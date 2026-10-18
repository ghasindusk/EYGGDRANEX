import 'package:eyggdranex_mobile/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('vanilla world can start, pause, and open rules/results', (
    tester,
  ) async {
    await tester.pumpWidget(const EyggdranexApp());
    expect(find.text('世界を観察する'), findsOneWidget);
    await tester.scrollUntilVisible(find.text('開始'), 300);
    await tester.tap(find.text('開始'));
    await tester.pump(const Duration(milliseconds: 120));
    expect(find.text('一時停止'), findsOneWidget);
    await tester.tap(find.text('一時停止'));
    await tester.tap(find.text('ルール'));
    await tester.pumpAndSettle();
    expect(find.text('バニラに戻す'), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, -1200));
    await tester.pumpAndSettle();
    expect(find.byType(Switch), findsWidgets);
    await tester.tap(find.text('結果'));
    await tester.pumpAndSettle();
    expect(find.text('実験結果'), findsOneWidget);
    await tester.drag(find.byType(ListView).first, const Offset(0, -1200));
    await tester.pumpAndSettle();
    expect(find.text('条件と結果を共有 (JSON)'), findsOneWidget);
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
    await tester.pumpWidget(const EyggdranexApp());
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
}
