# Google Play リリースの準備

EYGGDRANEX モバイル版を Google Play で公開するための確認事項です。**公開（Play Console への提出・審査依頼・製品版の配信）は SHAR-K の明示的な承認があるまで行いません。**

## 1. セキュリティ確認（2026-10-18、Claude）

対象: `mobile/`（Flutter / Kotlin）、版 0.4.0。ソースの読み取り確認で、実機での攻撃試験はしていません。

| 項目 | 状態 | 内容 |
|---|---|---|
| ネットワーク | ⚠ 広告で変更 | 0.4.0 までは `INTERNET` 権限なし（0.3.0 の APK を `aapt2 dump permissions` で確認）。0.5.0 で AdMob のバナー広告を入れたため `INTERNET` と、広告 SDK が宣言する `ACCESS_NETWORK_STATE`・`AD_ID` を持つ。通信するのは広告 SDK だけで、アプリ自身はシミュレーションのデータを送らない。targetSdk は 36 |
| 端末のストレージ | ✅ | 端末全体のストレージ権限を要求しない。フォルダは Android の文書プロバイダ（SAF）で、ユーザーが選んだフォルダだけを読む。永続的なアクセス権（`takePersistableUriPermission`）も取らない |
| 読み込むデータ | ✅ | 最大 20 ファイル・各先頭 1 MB・走査 5,000 件まで。バイト列を zlib 圧縮後の大きさと位置のハッシュに使うだけで、解釈・実行しない |
| 公開コンポーネント | ✅ | 外部に公開しているのはランチャーの Activity だけ。前景サービスは `exported="false"` |
| PendingIntent | ✅ | `FLAG_IMMUTABLE` |
| バックアップ | ✅ 修正 | `allowBackup="false"` とデータ抽出ルールで、クラウドバックアップと端末間転送から除外（保存するのは通知許可を尋ねたかどうかだけ） |
| ウェイクロック | ✅ 修正 | 時間制限なしだったものを 6 時間で自動解除に変更。一時停止・リセット・絶滅・アプリ終了でも解除 |
| 署名 | ✅ 修正 | Release がデバッグ鍵で署名されていた。`android/key.properties` があればアップロード鍵で署名するよう変更（鍵はリポジトリに入れない。`.gitignore` 済み） |
| 前景サービスの種類 | ⚠ 審査リスク | `specialUse`。Play Console で用途の申告が必要で、審査で認められない可能性がある（下の 3 を参照） |
| 共有する JSON | ℹ | ユーザーが共有を選んだときだけ、フォルダ名と相対ファイル名・サイズを含む（中身は含まない）。プライバシーポリシーに記載 |
| 広告と同意 | ✅ | AdMob のバナー（世界・ルールのタブの下）。Google の User Messaging Platform で、必要な地域（EEA・英国など）では同意を得てから広告を読み込む。結果のタブから同意をやり直せる（必要な地域のみ表示）。デバッグビルドは常に Google のテスト ID |
| 依存パッケージ | ℹ | `share_plus`（共有シート）、`google_mobile_ads` 9.1.0（広告と同意）。公開前に `flutter pub outdated` で更新を確認する |

## 2. コードとビルドで済んでいること

- アプリ ID: `com.eyggdranex.mobile`（`com.example` ではない）
- アダプティブアイコンとテーマアイコン（Android 13 以降のモノクロ）
- `flutter build appbundle` の確認を CI（`mobile-apk.yml`）に追加。CI の AAB はデバッグ鍵で署名されるので**提出には使えない**
- ストア用の画像の下書き: `store/icon-512.png`（512×512）、`store/feature-graphic-1024x500.png`
- プライバシーポリシーの下書き: `PRIVACY_POLICY.md`
- AdMob のバナー広告と同意フォーム（0.5.0）。ID は `android/admob.properties`（コミットしない）から読む。ファイルがなければ Google のテスト ID

## 3. SHAR-K が行うこと

1. **Google Play デベロッパーアカウント**の登録（登録料あり。個人アカウントは公開前に 12 人以上・14 日間のクローズドテストが必要）
2. **アップロード鍵の作成**（パスワードは自分で決めて保管。AI には渡さない）
   ```bash
   keytool -genkey -v -keystore %USERPROFILE%\eyggdranex-upload.jks -keyalg RSA -keysize 2048 -validity 10000 -alias upload
   ```
   `mobile/android/key.properties`（コミットしない）:
   ```
   storePassword=...
   keyPassword=...
   keyAlias=upload
   storeFile=C:/Users/<you>/eyggdranex-upload.jks
   ```
   Play App Signing を使う（Google が配信用の鍵を管理し、アップロード鍵は再発行できる）
3. **署名した AAB を作る**: `cd mobile && flutter build appbundle --release`（日本語を含むパスでは Gradle が失敗することがあるので、英数字だけのパスにコピーして実行）。成果物は `build/app/outputs/bundle/release/app-release.aab`
4. **プライバシーポリシーを公開 URL に置く**（例: GitHub のファイル URL や GitHub Pages）
4b. **AdMob の設定**
   - AdMob でこのアプリ（パッケージ名 `com.eyggdranex.mobile`）を追加し、**バナー**の広告ユニットを作る
   - `mobile/android/admob.properties`（コミットしない）:
     ```
     appId=ca-app-pub-XXXXXXXXXXXXXXXX~YYYYYYYYYY
     bannerId=ca-app-pub-XXXXXXXXXXXXXXXX/ZZZZZZZZZZ
     ```
   - AdMob の「プライバシーとメッセージ」で、GDPR の同意メッセージを作成・公開する（これがないと EEA・英国で広告が出ない）
   - Play の掲載情報にデベロッパーのウェブサイトを登録し、そのサイトの直下に `app-ads.txt` を置く（AdMob の画面に内容が表示される）
   - **自分の広告をタップしない**。実機で確認するときはデバッグビルド（テスト広告）か、AdMob にテスト端末を登録する
5. **Play Console の申告**
   - 広告: 「広告を含む」を選ぶ
   - データセーフティ: アプリ自身はデータを収集しない。ただし AdMob の SDK が、広告と分析のためにデバイス ID（広告 ID）、おおよその位置（IP アドレスから）、アプリの利用状況、診断情報を収集・共有する。Google の「Google Mobile Ads SDK のデータ開示」に従って申告する
   - ターゲット層: 子ども向けにしない（13 歳以上など）。子どもを含めると広告に制限がかかる
   - 前景サービス: `specialUse` の用途説明（ユーザーが開始したシミュレーションを画面オフ中も続けるため）。動画での説明を求められることがある。認められない場合は、バックグラウンド実行を外して申請し直す
   - 通知の権限、コンテンツのレーティング（暴力・課金などなし）、ターゲット層、広告なし
6. **ストアの掲載情報**: アプリ名、短い説明・詳しい説明、スクリーンショット（実機で撮影）、上の画像
7. クローズドテスト → 製品版の順に公開

## 4. 未確認

- 実機での動作（バックグラウンド実行・通知・電池消費、アイコンの見え方）
- 署名した AAB のビルド（鍵がないため）
- Play の審査結果
- 実機での広告の表示と同意フォーム（テスト ID・本番 ID とも）
