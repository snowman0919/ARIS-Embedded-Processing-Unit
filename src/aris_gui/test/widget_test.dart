import 'package:aris_gui/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<void> pumpConsole(WidgetTester tester) async {
    tester.view.devicePixelRatio = 1.0;
    tester.view.physicalSize = const Size(1280, 800);
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(const ArisGuiApp());
    await tester.pump(const Duration(milliseconds: 100));
  }

  testWidgets('operator console exposes core HMI panels', (tester) async {
    await pumpConsole(tester);

    expect(find.text('ARIS Console'), findsOneWidget);
    expect(find.text('Map Viewer'), findsOneWidget);
    expect(find.text('Mission'), findsOneWidget);
    expect(find.text('Vehicle'), findsOneWidget);
    expect(find.text('Safety'), findsOneWidget);
    expect(find.text('Review'), findsOneWidget);
    expect(find.text('Event Log'), findsOneWidget);
    expect(find.text('v3-semantic-route-20260621'), findsOneWidget);
  });

  testWidgets('safety controls latch and clear E-stop', (tester) async {
    await pumpConsole(tester);

    await tester.tap(find.widgetWithText(FilledButton, 'Latch').first);
    await tester.pumpAndSettle();
    expect(find.text('latched'), findsOneWidget);

    await tester.tap(find.widgetWithText(OutlinedButton, 'Clear'));
    await tester.pumpAndSettle();
    expect(find.text('clear'), findsOneWidget);
  });

  testWidgets('mission and review controls respond on 8.8 inch layout', (
    tester,
  ) async {
    await pumpConsole(tester);

    await tester.tap(find.widgetWithText(FilledButton, 'Hold route'));
    await tester.pumpAndSettle();
    expect(find.text('Resume route'), findsOneWidget);

    await tester.tap(find.byIcon(Icons.done).first);
    await tester.pumpAndSettle();
    expect(find.textContaining('map change chg-118 approved'), findsOneWidget);
  });
}
