import 'package:eyggdranex_mobile/ads.dart';
import 'package:eyggdranex_mobile/background_run.dart';
import 'package:eyggdranex_mobile/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

class FakeBackgroundRunner extends BackgroundRunController {
  int starts = 0;
  int stops = 0;
  bool allowed = true;

  @override
  Future<bool> start() async {
    starts++;
    return allowed;
  }

  @override
  Future<void> stop() async {
    stops++;
  }

  bool notifications = true;
  int settingsOpened = 0;

  @override
  Future<BackgroundStatus> status() async =>
      BackgroundStatus(notificationsEnabled: notifications, version: '0.4.0');

  @override
  Future<void> openNotificationSettings() async {
    settingsOpened++;
  }
}

Finder _scrollable(String key) => find.descendant(
  of: find.byKey(Key(key)),
  matching: find.byType(Scrollable),
);

void main() {
  testWidgets('vanilla world can start, pause, and open rules/results', (
    tester,
  ) async {
    final background = FakeBackgroundRunner();
    await tester.pumpWidget(
      EyggdranexApp(backgroundRunner: background, ads: NoAds()),
    );
    expect(find.text('世界を観察する'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('開始'), 300);
    await tester.tap(find.text('開始'));
    await tester.pump(const Duration(milliseconds: 120));
    expect(find.text('一時停止'), findsOneWidget);
    await tester.tap(find.text('一時停止'));
    expect(background.starts, 1);
    expect(background.stops, 1);
    await tester.tap(find.text('ルール'));
    await tester.pumpAndSettle();
    expect(find.text('バニラに戻す'), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, -1200));
    await tester.pumpAndSettle();
    expect(find.byType(Switch), findsWidgets);
    await tester.tap(find.text('結果'));
    await tester.pumpAndSettle();
    expect(find.text('実験結果'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.text('条件と結果を共有 (JSON)'),
      400,
      scrollable: _scrollable('results-list'),
    );
    expect(find.text('条件と結果を共有 (JSON)'), findsOneWidget);
  });

  testWidgets('results explain gene changes, mutations and lineages', (
    tester,
  ) async {
    await tester.pumpWidget(
      EyggdranexApp(backgroundRunner: FakeBackgroundRunner(), ads: NoAds()),
    );
    await tester.scrollUntilVisible(find.text('開始'), 300);
    await tester.tap(find.text('開始'));
    await tester.pump(const Duration(seconds: 3));
    await tester.tap(find.text('一時停止'));
    await tester.tap(find.text('結果'));
    await tester.pumpAndSettle();
    final results = _scrollable('results-list');
    for (final label in ['遺伝子の変化', '速度', '突然変異', '系統', '食べた餌']) {
      await tester.scrollUntilVisible(
        find.text(label),
        300,
        scrollable: results,
      );
      expect(find.text(label), findsWidgets);
    }
    expect(find.textContaining('生き残っている系統'), findsOneWidget);
  });

  testWidgets('legend chips hide and show map layers', (tester) async {
    await tester.pumpWidget(
      EyggdranexApp(backgroundRunner: FakeBackgroundRunner(), ads: NoAds()),
    );
    final chip = find.widgetWithText(FilterChip, '再生する餌  55');
    await tester.scrollUntilVisible(
      chip,
      200,
      scrollable: _scrollable('world-list'),
    );
    await tester.tap(chip);
    await tester.pump();
    final painter =
        tester
                .widget<CustomPaint>(
                  find.byWidgetPredicate(
                    (w) => w is CustomPaint && w.painter is WorldPainter,
                  ),
                )
                .painter!
            as WorldPainter;
    expect(painter.hidden, contains(Layer.renewable));
    expect(find.text('世界にあるもの'), findsOneWidget);
  });

  testWidgets('disabled notifications are explained while running', (
    tester,
  ) async {
    final background = FakeBackgroundRunner()..notifications = false;
    await tester.pumpWidget(
      EyggdranexApp(backgroundRunner: background, ads: NoAds()),
    );
    await tester.pump();
    await tester.scrollUntilVisible(find.text('開始'), 300);
    await tester.tap(find.text('開始'));
    await tester.pump(const Duration(milliseconds: 120));
    await tester.scrollUntilVisible(
      find.text('通知を許可'),
      200,
      scrollable: _scrollable('world-list'),
    );
    await tester.tap(find.text('通知を許可'));
    expect(background.settingsOpened, 1);
    await tester.tap(find.text('一時停止'));
  });

  testWidgets('simulation keeps ticking while app is backgrounded', (
    tester,
  ) async {
    final background = FakeBackgroundRunner();
    await tester.pumpWidget(
      EyggdranexApp(backgroundRunner: background, ads: NoAds()),
    );
    await tester.scrollUntilVisible(find.text('開始'), 300);
    await tester.tap(find.text('開始'));
    await tester.pump(const Duration(milliseconds: 120));
    final world = tester.widget<CustomPaint>(
      find.byWidgetPredicate(
        (widget) => widget is CustomPaint && widget.painter is WorldPainter,
      ),
    );
    final sim = (world.painter! as WorldPainter).sim;
    final before = sim.tickIndex;
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    await tester.pump(const Duration(milliseconds: 250));
    expect(sim.tickIndex, greaterThan(before));
    expect(background.stops, 0);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    await tester.tap(find.text('一時停止'));
    await tester.pump();
    expect(background.stops, 1);
    final pausedAt = sim.tickIndex;
    await tester.pump(const Duration(milliseconds: 150));
    expect(sim.tickIndex, pausedAt);
  });

  testWidgets('failed foreground service start leaves simulation paused', (
    tester,
  ) async {
    final background = FakeBackgroundRunner()..allowed = false;
    await tester.pumpWidget(
      EyggdranexApp(backgroundRunner: background, ads: NoAds()),
    );
    await tester.scrollUntilVisible(find.text('開始'), 300);
    await tester.tap(find.text('開始'));
    await tester.pumpAndSettle();
    expect(background.starts, 1);
    expect(find.text('開始'), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, 1200));
    await tester.pumpAndSettle();
    expect(find.textContaining('バックグラウンド実行を開始できませんでした'), findsOneWidget);
  });

  testWidgets('a selected folder supplies food files and shows its name', (
    tester,
  ) async {
    const channel = MethodChannel('eyggdranex.mobile/food_folder');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, (call) async {
          expect(call.method, 'pickFoodFolder');
          return {
            'folder': '研究データ',
            'files': [
              {
                'name': 'sub/food.txt',
                'bytes': Uint8List.fromList([1, 2, 3]),
              },
            ],
          };
        });
    addTearDown(
      () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, null),
    );
    await tester.pumpWidget(EyggdranexApp(ads: NoAds()));
    await tester.tap(find.text('ルール'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(
      find.text('餌のフォルダを選択'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.tap(find.text('餌のフォルダを選択').first);
    await tester.pumpAndSettle();
    expect(find.text('研究データ  •  1件のファイル'), findsOneWidget);
    expect(find.text('sub/food.txt'), findsOneWidget);
  });

  testWidgets(
    'privacy options appear when the consent platform requires them',
    (tester) async {
      final ads = NoAds()..privacyOptionsRequired.value = true;
      await tester.pumpWidget(
        EyggdranexApp(backgroundRunner: FakeBackgroundRunner(), ads: ads),
      );
      await tester.tap(find.text('結果'));
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('広告のプライバシー設定'),
        400,
        scrollable: _scrollable('results-list'),
      );
      expect(find.text('広告のプライバシー設定'), findsOneWidget);
    },
  );
}
