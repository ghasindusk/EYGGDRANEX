// Copyright (c) 2026 SHAR-K. MPL-2.0.
// Mobile model: the rules follow GENESIS, but Dart RNG and floating point order
// do not reproduce Python simulation-contract digests.
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

const _lo = <double>[.15, 1, 12, .20, .005, 80, .01, .05];
const _hi = <double>[4, 30, 120, .70, .25, 2000, 100, 1];
const _initial = <double>[1, 8, 28, .42, .06, 420, 1, .625];
const geneLower = _lo;
const geneUpper = _hi;
const geneInitial = _initial;
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

/// One-line meaning of each gene, shown in the results screen.
const geneHelp = <String>[
  '1 tick に動ける距離。速いほど移動コストが増える',
  '餌を見つけられる距離。広いほど代謝コストが増える',
  'このエネルギーに達すると子を産む',
  '産むときに子へ渡すエネルギーの割合',
  '子が親からどれだけずれるか（変異の大きさ自体も遺伝する）',
  '生きられる最大 tick。長いほど代謝コストが増える',
  '遠い餌をどれだけ避けるか',
  '餌が見えないときにさまよう歩幅',
];

/// A birth whose genes changed noticeably from the parent's.
class MutationEvent {
  final int tick, childId, parentId, generation, gene;
  final double ratio;
  const MutationEvent(
    this.tick,
    this.childId,
    this.parentId,
    this.generation,
    this.gene,
    this.ratio,
  );
}

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

  /// Id of the founder this individual descends from (its own id for founders).
  final int lineage;
  Life(
    this.id,
    this.x,
    this.y,
    this.energy,
    this.genes, [
    this.generation = 0,
    int? lineage,
  ]) : lineage = lineage ?? id;
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

  /// Tick of each history sample. Sampling starts every 10 ticks and halves the
  /// resolution whenever the history grows past [_maxSamples], so a long run keeps
  /// its beginning instead of dropping it.
  final List<int> historyTicks = [];
  final List<int> birthsHistory = [];

  /// Mean of each gene at every history sample.
  final List<List<double>> geneHistory = [];
  late final List<double> founderMeans;
  int sampleEvery = 10;
  static const _maxSamples = 600;
  int tickIndex = 0, births = 0, deaths = 0, maxGeneration = 0, nextId = 0;
  double eaten = 0;

  /// Energy eaten in total, by kind of food.
  double eatenRenewable = 0, eatenFile = 0, eatenDetritus = 0;

  /// Births whose genes differ from the parent's.
  int mutatedBirths = 0;

  /// Sum of |log(child / parent)| per gene over all births, and the count of
  /// births where some gene changed by more than [largeMutation] in log space.
  final List<double> mutationSum = List.filled(8, 0);
  int largeMutations = 0;
  static const largeMutation = .10;

  /// Most recent large mutations, newest last.
  final List<MutationEvent> recentMutations = [];

  MobileSimulation(SimRules input, List<FoodFile> inputFiles)
    : rules = input.copy(),
      files = List.unmodifiable(inputFiles) {
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
    founderMeans = List.generate(8, meanGene);
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
      if (p.food) {
        eatenFile += amount;
      } else if (p.regen < 0) {
        eatenDetritus += amount;
      } else {
        eatenRenewable += amount;
      }
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
          o.lineage,
        );
        _recordMutation(o, child);
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
    if (tickIndex % sampleEvery == 0 || life.isEmpty) _sample();
  }

  void _recordMutation(Life parent, Life child) {
    var biggest = 0, biggestSize = 0.0;
    for (var i = 0; i < 8; i++) {
      final size = (log(child.genes[i]) - log(parent.genes[i])).abs();
      mutationSum[i] += size;
      if (size > biggestSize) {
        biggest = i;
        biggestSize = size;
      }
    }
    if (biggestSize > 0) mutatedBirths++;
    if (biggestSize > largeMutation) {
      largeMutations++;
      recentMutations.add(
        MutationEvent(
          tickIndex,
          child.id,
          parent.id,
          child.generation,
          biggest,
          child.genes[biggest] / parent.genes[biggest],
        ),
      );
      if (recentMutations.length > 30) recentMutations.removeAt(0);
    }
  }

  void _sample() {
    if (historyTicks.isNotEmpty && historyTicks.last == tickIndex) return;
    historyTicks.add(tickIndex);
    populationHistory.add(life.length);
    generationHistory.add(maxGeneration);
    birthsHistory.add(births);
    geneHistory.add(List.generate(8, meanGene));
    if (historyTicks.length > _maxSamples) {
      // Keep every other sample, oldest first, and sample half as often from now on.
      _halve(historyTicks);
      _halve(populationHistory);
      _halve(generationHistory);
      _halve(birthsHistory);
      _halve(geneHistory);
      sampleEvery *= 2;
    }
  }

  static void _halve<T>(List<T> list) {
    final kept = [for (var i = 0; i < list.length; i += 2) list[i]];
    list
      ..clear()
      ..addAll(kept);
  }

  /// Ticks until the next file-food regrowth, or null when regrowth is off.
  int? get ticksToRegrow => rules.regrowInterval > 0 && foodPatches.isNotEmpty
      ? rules.regrowInterval - tickIndex % rules.regrowInterval
      : null;

  int get renewableCount =>
      patches.where((p) => !p.food && p.regen >= 0).length;
  int get detritusCount => patches.where((p) => !p.food && p.regen < 0).length;
  int get fileFoodCount => patches.where((p) => p.food).length;
  double get renewableEnergy => patches
      .where((p) => !p.food && p.regen >= 0)
      .fold(0.0, (sum, p) => sum + p.energy);

  /// Total energy the file food started with.
  double get fileFoodTotal =>
      foodTemplates.fold(0.0, (sum, p) => sum + p.energy + (p.reservoir ?? 0));

  /// Living individuals per founder lineage, largest first.
  List<MapEntry<int, int>> lineages() {
    final counts = <int, int>{};
    for (final o in life) {
      counts[o.lineage] = (counts[o.lineage] ?? 0) + 1;
    }
    return counts.entries.toList()..sort((a, b) => b.value.compareTo(a.value));
  }

  /// Minimum and maximum of a gene in the living population.
  (double, double) geneRange(int i) {
    if (life.isEmpty) return (0, 0);
    var lo = double.infinity, hi = double.negativeInfinity;
    for (final o in life) {
      lo = min(lo, o.genes[i]);
      hi = max(hi, o.genes[i]);
    }
    return (lo, hi);
  }

  /// Typical size of a mutation in gene [i] per birth, as a fraction (0.05 = 5%).
  double meanMutation(int i) =>
      births == 0 ? 0 : exp(mutationSum[i] / births) - 1;

  double meanGene(int i) => life.isEmpty
      ? 0
      : life.map((o) => o.genes[i]).reduce((a, b) => a + b) / life.length;
  double get foodEnergy => patches
      .where((p) => p.food)
      .fold(0.0, (sum, p) => sum + p.energy + (p.reservoir ?? 0));
}
