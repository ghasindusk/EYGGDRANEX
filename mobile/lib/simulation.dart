// Copyright (c) 2026 SHAR-K. MPL-2.0.
// Mobile model: the rules follow GENESIS, but Dart RNG and floating point order
// do not reproduce Python simulation-contract digests.
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

const _lo = <double>[.15, 1, 12, .20, .005, 80, .01, .05];
const _hi = <double>[4, 30, 120, .70, .25, 2000, 100, 1];
const _initial = <double>[1, 8, 28, .42, .06, 420, 1, .625];
const geneNames = <String>[
  '速度',
  '感覚範囲',
  '繁殖閾値',
  '子への配分',
  '変異幅',
  '寿命',
  '距離選好',
  '探索幅',
];

class FoodFile {
  final String name;
  final Uint8List bytes;
  FoodFile(this.name, this.bytes);
}

class SimRules {
  int seed = 42;
  int founders = 60;
  int resourcePatches = 55;
  double resourceRegeneration = 1;
  double metabolism = 1;
  double movementCost = 1;
  bool mutation = true;
  bool detritus = false;
  int regrowInterval = 0;
  bool useFood = false;

  SimRules copy() => SimRules()
    ..seed = seed
    ..founders = founders
    ..resourcePatches = resourcePatches
    ..resourceRegeneration = resourceRegeneration
    ..metabolism = metabolism
    ..movementCost = movementCost
    ..mutation = mutation
    ..detritus = detritus
    ..regrowInterval = regrowInterval
    ..useFood = useFood;

  Map<String, Object> toJson() => {
    'seed': seed,
    'founders': founders,
    'resourcePatches': resourcePatches,
    'resourceRegeneration': resourceRegeneration,
    'metabolism': metabolism,
    'movementCost': movementCost,
    'mutation': mutation,
    'detritus': detritus,
    'regrowInterval': regrowInterval,
    'useFood': useFood,
  };
}

class Life {
  final int id;
  int generation;
  int age = 0;
  double x, y, energy;
  List<double> genes;
  Life(this.id, this.x, this.y, this.energy, this.genes, [this.generation = 0]);
  bool get alive => energy > 0 && age < genes[5];
}

class Patch {
  final double x, y;
  double energy, capacity, regen;
  double? reservoir;
  final bool food;
  Patch(
    this.x,
    this.y,
    this.energy,
    this.capacity,
    this.regen, {
    this.reservoir,
    this.food = false,
  });

  void tick() {
    if (reservoir == null) {
      energy = (energy + regen).clamp(0, capacity);
    } else {
      final amount = min(regen, min(reservoir!, capacity - energy));
      if (amount > 0) {
        energy += amount;
        reservoir = reservoir! - amount;
      }
    }
  }

  bool get exhausted =>
      energy <= 0 && (regen <= 0 || (reservoir != null && reservoir! <= 0));
}

class MobileSimulation {
  final SimRules rules;
  final List<FoodFile> files;
  late final Random worldRng,
      founderRng,
      movementRng,
      placementRng,
      mutationRng;
  final List<Life> life = [];
  final List<Patch> patches = [];
  final List<Patch> foodTemplates = [];
  final List<Patch> foodPatches = [];
  final List<int> populationHistory = [];
  final List<int> generationHistory = [];
  int tickIndex = 0, births = 0, deaths = 0, maxGeneration = 0, nextId = 0;
  double eaten = 0;

  MobileSimulation(SimRules input, this.files) : rules = input.copy() {
    worldRng = Random(_seed(1));
    founderRng = Random(_seed(2));
    movementRng = Random(_seed(3));
    placementRng = Random(_seed(4));
    mutationRng = Random(_seed(5));
    for (var i = 0; i < rules.resourcePatches; i++) {
      final x = worldRng.nextDouble() * 100, y = worldRng.nextDouble() * 100;
      final energy = _uniform(worldRng, 18, 34);
      final capacity = _uniform(worldRng, 26, 46);
      patches.add(
        Patch(
          x,
          y,
          min(energy, capacity),
          capacity,
          _uniform(worldRng, .18, .55) * rules.resourceRegeneration,
        ),
      );
    }
    if (rules.useFood) _loadFood();
    for (var i = 0; i < rules.founders; i++) {
      life.add(
        Life(
          nextId++,
          founderRng.nextDouble() * 100,
          founderRng.nextDouble() * 100,
          _uniform(founderRng, 16, 26),
          _mutate(_initial, founderRng),
        ),
      );
    }
    _sample();
  }

  int _seed(int stream) =>
      ((rules.seed * 1103515245) ^ (stream * 2654435761)) & 0x7fffffff;
  double _uniform(Random r, double a, double b) => a + r.nextDouble() * (b - a);
  double _gauss(Random r) =>
      sqrt(-2 * log(max(1e-12, r.nextDouble()))) * cos(2 * pi * r.nextDouble());
  double _reflect(double v, double lo, double hi) {
    final span = hi - lo;
    final t = ((v - lo) % (2 * span) + 2 * span) % (2 * span);
    return lo + (t <= span ? t : 2 * span - t);
  }

  List<double> _mutate(List<double> genes, Random r) => List.generate(8, (i) {
    final v = log(genes[i]) + _gauss(r) * genes[4];
    return exp(_reflect(v, log(_lo[i]), log(_hi[i]))).clamp(_lo[i], _hi[i]);
  });
  double _wrap(double n) => (n % 100 + 100) % 100;
  double _delta(double from, double to) => (to - from + 50 + 100) % 100 - 50;
  double _distance(Life o, Patch p) =>
      sqrt(pow(_delta(o.x, p.x), 2) + pow(_delta(o.y, p.y), 2));

  void _loadFood() {
    // Same basic energy formula as Python: compressed bytes * 0.01. Limit memory
    // on a phone to 20 files and 1 MB each; never parse or execute their contents.
    for (final file in files.take(20)) {
      final bytes = file.bytes.length > 1000000
          ? Uint8List.sublistView(file.bytes, 0, 1000000)
          : file.bytes;
      if (bytes.isEmpty) continue;
      final compressed = ZLibEncoder(level: 9).convert(bytes).length;
      final energy = min(10000.0, compressed * .01);
      // Position depends on bytes, not file name. A deterministic 32-bit hash
      // places data independently from the world RNG stream.
      var hashX = 2166136261, hashY = 16777619;
      for (final b in bytes) {
        hashX = ((hashX ^ b) * 16777619) & 0xffffffff;
        hashY = ((hashY ^ b) * 2246822519) & 0xffffffff;
      }
      final x = hashX / 0x100000000 * 100;
      final y = hashY / 0x100000000 * 100;
      final exposed = min(energy, 30.0);
      final patch = Patch(
        x,
        y,
        exposed,
        30,
        .4,
        reservoir: energy - exposed,
        food: true,
      );
      patches.add(patch);
      foodPatches.add(patch);
      foodTemplates.add(
        Patch(x, y, exposed, 30, .4, reservoir: energy - exposed, food: true),
      );
    }
  }

  void tick() {
    tickIndex++;
    for (final p in patches) {
      p.tick();
    }
    patches.removeWhere((p) => p.exhausted);
    if (rules.regrowInterval > 0 && tickIndex % rules.regrowInterval == 0) {
      for (var i = 0; i < foodPatches.length; i++) {
        final p = foodPatches[i], t = foodTemplates[i];
        p.energy = t.energy;
        p.capacity = t.capacity;
        p.regen = t.regen;
        p.reservoir = t.reservoir;
        if (!patches.contains(p)) patches.add(p);
      }
    }
    life.sort((a, b) => a.id.compareTo(b.id));
    // All movement choices see the same resources before feeding.
    final moves = <(double, double)>[];
    for (final o in life) {
      Patch? best;
      var bestScore = -1.0, bestDist = 0.0;
      for (final p in patches) {
        if (p.energy <= .2) continue;
        final d = _distance(o, p);
        if (d > o.genes[1]) continue;
        final score = p.energy / (1 + o.genes[6] * d);
        if (score > bestScore) {
          best = p;
          bestScore = score;
          bestDist = d;
        }
      }
      if (best == null) {
        final a = movementRng.nextDouble() * 2 * pi;
        final step = o.genes[0] * o.genes[7];
        moves.add((cos(a) * step, sin(a) * step));
      } else if (bestDist < 1e-12) {
        moves.add((0, 0));
      } else {
        final step = min(o.genes[0], bestDist) / bestDist;
        moves.add((_delta(o.x, best.x) * step, _delta(o.y, best.y) * step));
      }
    }
    for (var i = 0; i < life.length; i++) {
      final o = life[i], m = moves[i];
      o.age++;
      o.x = _wrap(o.x + m.$1);
      o.y = _wrap(o.y + m.$2);
      o.energy -=
          (.10 + .006 * o.genes[1] + .00017 * o.genes[5]) * rules.metabolism +
          sqrt(m.$1 * m.$1 + m.$2 * m.$2) *
              .04 *
              o.genes[0] *
              rules.movementCost;
    }
    final claims = <Patch, List<Life>>{};
    for (final o in life) {
      Patch? nearest;
      var distance = double.infinity;
      for (final p in patches) {
        if (p.energy <= .2) continue;
        final d = _distance(o, p);
        if (d <= 1.1 && d < distance) {
          nearest = p;
          distance = d;
        }
      }
      if (nearest != null) claims.putIfAbsent(nearest, () => []).add(o);
    }
    eaten = 0;
    for (final entry in claims.entries) {
      final p = entry.key, eaters = entry.value;
      final amount = min(p.energy, 3.0 * eaters.length);
      p.energy -= amount;
      eaten += amount;
      for (final o in eaters) {
        o.energy += amount / eaters.length;
      }
    }
    final newborn = <Life>[];
    for (final o in life) {
      if (o.alive && o.energy >= o.genes[2]) {
        final amount = o.energy * o.genes[3];
        o.energy -= amount;
        final a = placementRng.nextDouble() * 2 * pi;
        final child = Life(
          nextId++,
          _wrap(o.x + cos(a)),
          _wrap(o.y + sin(a)),
          amount,
          rules.mutation ? _mutate(o.genes, mutationRng) : List.of(o.genes),
          o.generation + 1,
        );
        newborn.add(child);
        maxGeneration = max(maxGeneration, child.generation);
      }
    }
    final survivors = <Life>[];
    for (final o in life) {
      if (o.alive) {
        survivors.add(o);
      } else {
        deaths++;
        final left = o.energy * (rules.detritus ? .5 : 0);
        if (left > 0) patches.add(Patch(o.x, o.y, left, left, -.05));
      }
    }
    births += newborn.length;
    life
      ..clear()
      ..addAll(survivors)
      ..addAll(newborn);
    if (tickIndex % 10 == 0 || life.isEmpty) _sample();
  }

  void _sample() {
    populationHistory.add(life.length);
    generationHistory.add(maxGeneration);
    if (populationHistory.length > 500) {
      populationHistory.removeAt(0);
      generationHistory.removeAt(0);
    }
  }

  double meanGene(int i) => life.isEmpty
      ? 0
      : life.map((o) => o.genes[i]).reduce((a, b) => a + b) / life.length;
  double get foodEnergy => patches
      .where((p) => p.food)
      .fold(0.0, (sum, p) => sum + p.energy + (p.reservoir ?? 0));
}
