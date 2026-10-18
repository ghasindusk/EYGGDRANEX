import 'package:flutter/services.dart';

/// State of the Android side that the app shows to the user.
class BackgroundStatus {
  const BackgroundStatus({this.notificationsEnabled = true, this.version = ''});

  final bool notificationsEnabled;
  final String version;
}

/// Controls the Android foreground service that keeps simulation ticks running.
class BackgroundRunController {
  const BackgroundRunController();

  static const _channel = MethodChannel('eyggdranex.mobile/background_run');

  Future<bool> start() async =>
      await _channel.invokeMethod<bool>('start') ?? false;

  Future<void> stop() async {
    await _channel.invokeMethod<bool>('stop');
  }

  Future<BackgroundStatus> status() async {
    try {
      final map = await _channel.invokeMapMethod<String, dynamic>('status');
      return BackgroundStatus(
        notificationsEnabled: map?['notificationsEnabled'] as bool? ?? true,
        version: map?['version'] as String? ?? '',
      );
    } on MissingPluginException {
      return const BackgroundStatus();
    }
  }

  Future<void> openNotificationSettings() async {
    await _channel.invokeMethod<bool>('openNotificationSettings');
  }
}
