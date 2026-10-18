# Room (used by WorkManager, which the Google Mobile Ads SDK pulls in) finds each
# database's generated implementation by name. Without these rules R8 renames or drops
# androidx.work.impl.WorkDatabase_Impl and the app crashes at startup
# ("Failed to create an instance of androidx.work.impl.WorkDatabase").
-keep class * extends androidx.room.RoomDatabase { <init>(); }
-keep class **_Impl extends androidx.room.RoomDatabase { *; }
-keep class androidx.work.impl.WorkDatabase_Impl { *; }
