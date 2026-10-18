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

  test(
    'records mutations, lineages and food intake without changing the run',
    () {
      final sim = MobileSimulation(SimRules(), []);
      for (var i = 0; i < 2000 && sim.life.isNotEmpty; i++) {
        sim.tick();
      }
      expect(sim.births, greaterThan(0));
      expect(sim.mutatedBirths, sim.births);
      expect(sim.meanMutation(0), greaterThan(0));
      expect(sim.eatenRenewable, greaterThan(0));
      expect(sim.eatenFile, 0);
      final lineages = sim.lineages();
      expect(lineages.fold(0, (sum, e) => sum + e.value), sim.life.length);
      expect(
        lineages.every((e) => e.key >= 0 && e.key < sim.rules.founders),
        isTrue,
      );
      expect(sim.founderMeans, hasLength(8));
      expect(sim.geneHistory.length, sim.historyTicks.length);
    },
  );

  test('history keeps the start of long runs at lower resolution', () {
    final rules = SimRules()..founders = 0;
    final sim = MobileSimulation(rules, []);
    // No individuals: each tick samples once (population is empty).
    for (var i = 0; i < 7000; i++) {
      sim.tick();
    }
    expect(sim.historyTicks.first, 0);
    expect(sim.historyTicks.length, lessThanOrEqualTo(601));
    expect(sim.populationHistory.length, sim.historyTicks.length);
  });

  test('fixed genome records no mutated births', () {
    final sim = MobileSimulation(SimRules()..mutation = false, []);
    for (var i = 0; i < 600; i++) {
      sim.tick();
    }
    expect(sim.births, greaterThan(0));
    expect(sim.mutatedBirths, 0);
    expect(sim.largeMutations, 0);
  });
}

bool _same(List<double> a, List<double> b) =>
    a.length == b.length &&
    List.generate(a.length, (i) => a[i] == b[i]).every((v) => v);
