package com.eyggdranex.mobile

import android.Manifest
import android.app.Activity
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.DocumentsContract
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.ByteArrayOutputStream
import java.util.ArrayDeque

class MainActivity : FlutterActivity() {
    private val channelName = "eyggdranex.mobile/food_folder"
    private val folderRequestCode = 4107
    private val notificationRequestCode = 4108
    private var pendingFolderResult: MethodChannel.Result? = null
    private var pendingStartResult: MethodChannel.Result? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, channelName)
            .setMethodCallHandler { call, result ->
                if (call.method != "pickFoodFolder") {
                    result.notImplemented()
                } else if (pendingFolderResult != null) {
                    result.error("BUSY", "A folder picker is already open", null)
                } else {
                    pendingFolderResult = result
                    val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
                        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                    }
                    try {
                        startActivityForResult(intent, folderRequestCode)
                    } catch (error: Exception) {
                        pendingFolderResult = null
                        result.error("PICKER", error.message, null)
                    }
                }
            }
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "eyggdranex.mobile/background_run")
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "start" -> {
                        if (pendingStartResult != null) {
                            result.error("BUSY", "Background start is already pending", null)
                        } else if (
                            Build.VERSION.SDK_INT >= 33 &&
                            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) !=
                            PackageManager.PERMISSION_GRANTED &&
                            !getPreferences(Context.MODE_PRIVATE)
                                .getBoolean("notification_prompted", false)
                        ) {
                            pendingStartResult = result
                            getPreferences(Context.MODE_PRIVATE).edit()
                                .putBoolean("notification_prompted", true).apply()
                            requestPermissions(
                                arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                                notificationRequestCode,
                            )
                        } else {
                            startSimulationService(result)
                        }
                    }
                    "stop" -> {
                        stopService(Intent(this, SimulationService::class.java))
                        result.success(true)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    private fun startSimulationService(result: MethodChannel.Result) {
        try {
            val intent = Intent(this, SimulationService::class.java)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                startForegroundService(intent)
            } else {
                startService(intent)
            }
            result.success(true)
        } catch (error: Exception) {
            result.error("BACKGROUND_START", error.message, null)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray,
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == notificationRequestCode) {
            val result = pendingStartResult ?: return
            pendingStartResult = null
            // Android can run a foreground service even if the drawer notification is denied.
            startSimulationService(result)
        }
    }

    @Deprecated("Android activity result bridge for the Flutter host activity")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode != folderRequestCode) return
        val result = pendingFolderResult ?: return
        pendingFolderResult = null
        val tree = data?.data
        if (resultCode != Activity.RESULT_OK || tree == null) {
            result.success(null)
            return
        }
        Thread {
            try {
                val selected = readFolder(tree)
                runOnUiThread { result.success(selected) }
            } catch (error: Exception) {
                runOnUiThread { result.error("READ_FOLDER", error.message, null) }
            }
        }.start()
    }

    private fun readFolder(tree: Uri): Map<String, Any> {
        val rootId = DocumentsContract.getTreeDocumentId(tree)
        val root = DocumentsContract.buildDocumentUriUsingTree(tree, rootId)
        val projection = arrayOf(
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE,
        )
        var folderName = "選択したフォルダ"
        contentResolver.query(root, projection, null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                folderName = cursor.getString(1) ?: folderName
            }
        }

        val files = mutableListOf<Map<String, Any>>()
        val folders = ArrayDeque<Pair<String, String>>()
        folders.add(rootId to "")
        var scanned = 0
        while (folders.isNotEmpty() && files.size < 20 && scanned < 5000) {
            val (parentId, path) = folders.removeFirst()
            val children = DocumentsContract.buildChildDocumentsUriUsingTree(tree, parentId)
            val entries = mutableListOf<Triple<String, String, String>>()
            contentResolver.query(children, projection, null, null, null)?.use { cursor ->
                while (cursor.moveToNext() && scanned < 5000) {
                    scanned++
                    entries.add(
                        Triple(
                            cursor.getString(0),
                            cursor.getString(1) ?: "unnamed",
                            cursor.getString(2) ?: "",
                        )
                    )
                }
            }
            for ((id, name, mimeType) in entries.sortedBy { it.second.lowercase() }) {
                val relativeName = if (path.isEmpty()) name else "$path/$name"
                if (mimeType == DocumentsContract.Document.MIME_TYPE_DIR) {
                    folders.add(id to relativeName)
                } else if (files.size < 20) {
                    val document = DocumentsContract.buildDocumentUriUsingTree(tree, id)
                    val bytes = readFirstMegabyte(document)
                    if (bytes.isNotEmpty()) {
                        files.add(mapOf("name" to relativeName, "bytes" to bytes))
                    }
                }
            }
        }
        return mapOf("folder" to folderName, "files" to files)
    }

    private fun readFirstMegabyte(document: Uri): ByteArray {
        contentResolver.openInputStream(document)?.use { stream ->
            val output = ByteArrayOutputStream()
            val buffer = ByteArray(8192)
            while (output.size() < 1_000_000) {
                val read = stream.read(buffer, 0, minOf(buffer.size, 1_000_000 - output.size()))
                if (read < 0) break
                output.write(buffer, 0, read)
            }
            return output.toByteArray()
        }
        return byteArrayOf()
    }
}
