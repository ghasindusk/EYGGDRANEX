import 'dart:typed_data';

import 'package:eyggdranex_mobile/simulation.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('same seed and rules produce the same mobile trajectory', () {
    final a = MobileSimulation(SimRules(), []);
    final b = MobileSimulation(SimRules(), []);
    for (var i = 0; i < 300; i++) {
      a.tick();
      b.tick();
    }
    expect(a.tickIndex, b.tickIndex);
    expect(a.life.length, b.life.length);
    expect(a.births, b.births);
    expect(a.maxGeneration, b.maxGeneration);
    expect(
      a.life.map((o) => [o.id, o.x, o.y, o.energy, ...o.genes]).toList(),
      b.life.map((o) => [o.id, o.x, o.y, o.energy, ...o.genes]).toList(),
    );
  });

  test('fixed genome offspring inherits the parent genome', () {
    final rules = SimRules()..mutation = false;
    final sim = MobileSimulation(rules, []);
    final founders = {for (final o in sim.life) o.id: List<double>.of(o.genes)};
    for (var i = 0; i < 300 && sim.births == 0; i++) {
      sim.tick();
    }
    expect(sim.births, greaterThan(0));
    // Every child must equal one of the initial genomes.
    for (final o in sim.life.where((o) => o.generation > 0)) {
      expect(founders.values.any((g) => _same(g, o.genes)), isTrue);
    }
  });

  test('food regrows on the selected interval', () {
    final rules = SimRules()
      ..founders = 0
      ..resourcePatches = 0
      ..useFood = true
      ..regrowInterval = 5;
    final sim = MobileSimulation(rules, [
      FoodFile(
        'a.txt',
        Uint8List.fromList(List.generate(3000, (i) => i % 251)),
      ),
    ]);
    expect(sim.foodPatches, hasLength(1));
    final original = sim.foodPatches.single.energy;
    sim.foodPatches.single.energy = 0;
    for (var i = 0; i < 5; i++) {
      sim.tick();
    }
    expect(sim.foodPatches.single.energy, original);
    expect(sim.patches.contains(sim.foodPatches.single), isTrue);
  });
}

bool _same(List<double> a, List<double> b) =>
    a.length == b.length &&
    List.generate(a.length, (i) => a[i] == b[i]).every((v) => v);
