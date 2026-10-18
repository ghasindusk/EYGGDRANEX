import 'package:eyggdranex_mobile/main.dart';
import 'package:flutter/material.dart';
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
}
