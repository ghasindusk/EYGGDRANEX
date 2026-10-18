// Copyright (c) 2026 SHAR-K. MPL-2.0.
import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

import 'simulation.dart';

void main() => runApp(const EyggdranexApp());

class EyggdranexApp extends StatelessWidget {
  const EyggdranexApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'EYGGDRANEX',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xff79e2a5),
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: const Color(0xff0b1417),
      cardTheme: CardThemeData(
        color: const Color(0xff12252a),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(20),
          side: const BorderSide(color: Color(0xff254147)),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: const Color(0xff12252a),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(14)),
      ),
      navigationBarTheme: const NavigationBarThemeData(
        backgroundColor: Color(0xff102125),
        indicatorColor: Color(0xff285443),
      ),
    ),
    home: const LabPage(),
  );
}

class LabPage extends StatefulWidget {
  const LabPage({super.key});
  @override
  State<LabPage> createState() => _LabPageState();
}

class _LabPageState extends State<LabPage> with WidgetsBindingObserver {
  SimRules draft = SimRules();
  late MobileSimulation sim;
  final List<FoodFile> files = [];
  String? foodFolderName;
  final seedController = TextEditingController(text: '42');
  Timer? timer;
  bool playing = false, dirty = false, loading = false;
  int tab = 0, ticksPerFrame = 1;
  String? error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    sim = MobileSimulation(draft, files);
  }

  @override
  void dispose() {
    timer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    seedController.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && playing) {
      timer?.cancel();
      setState(() => playing = false);
    }
  }

  void _play() {
    if (playing) {
      timer?.cancel();
      setState(() => playing = false);
      return;
    }
    if (sim.life.isEmpty) _reset();
    setState(() {
      playing = true;
      error = null;
    });
    timer = Timer.periodic(const Duration(milliseconds: 50), (_) {
      if (!mounted) return;
      try {
        // Yield after every small batch so controls stay responsive on a phone.
        for (var i = 0; i < ticksPerFrame && sim.life.isNotEmpty; i++) {
          sim.tick();
        }
        if (sim.life.isEmpty) {
          timer?.cancel();
          playing = false;
        }
        setState(() {});
      } catch (e) {
        timer?.cancel();
        setState(() {
          playing = false;
          error = '$e';
        });
      }
    });
  }

  void _reset() {
    timer?.cancel();
    final seed = int.tryParse(seedController.text.trim());
    if (seed == null) {
      setState(() {
        error = 'シードには整数を入力してください';
        playing = false;
      });
      return;
    }
    setState(() {
      playing = false;
      error = null;
      draft.seed = seed;
      sim = MobileSimulation(draft, files);
      dirty = false;
    });
  }

  void _change(void Function() update) => setState(() {
    update();
    dirty = true;
  });

  static const _foodFolderChannel = MethodChannel(
    'eyggdranex.mobile/food_folder',
  );

  Future<void> _pickFolder() async {
    if (loading) {
      return;
    }
    if (playing) {
      timer?.cancel();
      playing = false;
    }
    setState(() => loading = true);
    try {
      final picked = await _foodFolderChannel.invokeMapMethod<String, dynamic>(
        'pickFoodFolder',
      );
      if (picked == null || !mounted) return;
      final usable = <FoodFile>[
        for (final entry in (picked['files'] as List<dynamic>).cast<Map>())
          FoodFile(entry['name'] as String, entry['bytes'] as Uint8List),
      ];
      _change(() {
        files
          ..clear()
          ..addAll(usable);
        foodFolderName = picked['folder'] as String?;
        draft.useFood = usable.isNotEmpty;
      });
    } catch (e) {
      if (mounted) setState(() => error = 'フォルダを読み込めませんでした: $e');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  String _record() => const JsonEncoder.withIndent('  ').convert({
    'app': 'EYGGDRANEX mobile',
    'mobileModel': 1,
    'pythonContractDigestCompatible': false,
    'rules': sim.rules.toJson(),
    'foodFiles': sim.files
        .map((f) => {'name': f.name, 'bytes': f.bytes.length})
        .toList(),
    'foodFolder': foodFolderName,
    'tick': sim.tickIndex,
    'population': sim.life.length,
    'births': sim.births,
    'deaths': sim.deaths,
    'maxGeneration': sim.maxGeneration,
    'remainingFoodEnergy': sim.foodEnergy,
    'meanGenes': {
      for (var i = 0; i < geneNames.length; i++) geneNames[i]: sim.meanGene(i),
    },
    'populationHistory': sim.populationHistory,
    'generationHistory': sim.generationHistory,
  });

  Future<void> _share() async {
    try {
      await SharePlus.instance.share(
        ShareParams(text: _record(), subject: 'EYGGDRANEX 実験記録'),
      );
    } catch (_) {
      await Clipboard.setData(ClipboardData(text: _record()));
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('実験記録をクリップボードにコピーしました')));
      }
    }
  }

  Widget _tile(String title, String subtitle, Widget trailing) => Card(
    child: Padding(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
          trailing,
        ],
      ),
    ),
  );

  Widget _slider(
    String title,
    double value,
    double minValue,
    double maxValue,
    String label,
    ValueChanged<double> onChanged, {
    int? divisions,
  }) => Card(
    child: Padding(
      padding: const EdgeInsets.fromLTRB(14, 9, 14, 3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(child: Text(title)),
              Text(
                label,
                style: TextStyle(
                  color: Theme.of(context).colorScheme.primary,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ],
          ),
          Slider(
            value: value.clamp(minValue, maxValue),
            min: minValue,
            max: maxValue,
            divisions: divisions,
            onChanged: (v) => _change(() => onChanged(v)),
          ),
        ],
      ),
    ),
  );

  Widget _world() => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      _banner(),
      const SizedBox(height: 8),
      AspectRatio(
        aspectRatio: 1,
        child: Card(
          clipBehavior: Clip.antiAlias,
          child: CustomPaint(
            painter: WorldPainter(sim),
            child: const SizedBox.expand(),
          ),
        ),
      ),
      const SizedBox(height: 12),
      Row(
        children: [
          Expanded(child: _metric('TICK', '${sim.tickIndex}')),
          Expanded(child: _metric('個体', '${sim.life.length}')),
          Expanded(child: _metric('最大世代', '${sim.maxGeneration}')),
        ],
      ),
      const SizedBox(height: 12),
      Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: _play,
              icon: Icon(playing ? Icons.pause : Icons.play_arrow),
              label: Text(playing ? '一時停止' : '開始'),
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            onPressed: _reset,
            icon: const Icon(Icons.restart_alt),
            label: const Text('リセット'),
          ),
        ],
      ),
      const SizedBox(height: 8),
      SegmentedButton<int>(
        segments: const [
          ButtonSegment(value: 1, label: Text('ゆっくり')),
          ButtonSegment(value: 4, label: Text('標準')),
          ButtonSegment(value: 12, label: Text('高速')),
        ],
        selected: {ticksPerFrame},
        onSelectionChanged: (s) => setState(() => ticksPerFrame = s.first),
      ),
      const SizedBox(height: 10),
      if (sim.life.isEmpty) const Text('個体群が絶滅しました。ルールを変えて再実行できます。'),
      Text(
        '緑: 個体  •  青: 再生する餌  •  琥珀: ファイルの餌',
        style: Theme.of(context).textTheme.bodySmall,
      ),
    ],
  );

  Widget _banner() => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      if (dirty)
        Card(
          color: const Color(0xff51411f),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                const Expanded(child: Text('ルールの変更は次のリセットから反映されます')),
                TextButton(onPressed: _reset, child: const Text('反映')),
              ],
            ),
          ),
        ),
      if (error != null)
        Card(
          color: const Color(0xff622c30),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Text(error!),
          ),
        ),
      Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          gradient: const LinearGradient(
            colors: [Color(0xff173c39), Color(0xff12252a)],
          ),
          border: Border.all(color: const Color(0xff366351)),
        ),
        child: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.asset(
                'assets/brand/eyggdranex-mark.png',
                width: 72,
                height: 72,
              ),
            ),
            const SizedBox(width: 14),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '世界を観察する',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(height: 4),
                  Text('種から始まる、手のひらの生態系。'),
                ],
              ),
            ),
          ],
        ),
      ),
    ],
  );

  Widget _metric(String name, String value) => Card(
    child: Padding(
      padding: const EdgeInsets.all(10),
      child: Column(
        children: [
          Text(
            value,
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
          ),
          Text(name, style: Theme.of(context).textTheme.labelSmall),
        ],
      ),
    ),
  );

  Widget _rules() => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      const Text(
        'ルールを組み立てる',
        style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 4),
      Text(
        '初期値がバニラです。変更は「反映してリセット」で新しい世界に適用します。',
        style: Theme.of(context).textTheme.bodySmall,
      ),
      const SizedBox(height: 14),
      Row(
        children: [
          Expanded(
            child: OutlinedButton.icon(
              onPressed: () {
                _change(() {
                  draft = SimRules();
                  seedController.text = '42';
                });
              },
              icon: const Icon(Icons.layers_clear),
              label: const Text('バニラに戻す'),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: FilledButton(
              onPressed: _reset,
              child: const Text('反映してリセット'),
            ),
          ),
        ],
      ),
      const SizedBox(height: 14),
      TextField(
        controller: seedController,
        keyboardType: const TextInputType.numberWithOptions(signed: true),
        decoration: const InputDecoration(
          labelText: 'シード',
          border: OutlineInputBorder(),
          helperText: '同じ設定とシードならモバイル版で再実行できます',
        ),
        onChanged: (_) => setState(() => dirty = true),
      ),
      const SizedBox(height: 12),
      _slider(
        '創始個体',
        draft.founders.toDouble(),
        0,
        200,
        '${draft.founders}',
        (v) => draft.founders = v.round(),
        divisions: 200,
      ),
      _slider(
        '再生する餌の数',
        draft.resourcePatches.toDouble(),
        0,
        150,
        '${draft.resourcePatches}',
        (v) => draft.resourcePatches = v.round(),
        divisions: 150,
      ),
      _slider(
        '餌の再生倍率',
        draft.resourceRegeneration,
        0,
        3,
        '${draft.resourceRegeneration.toStringAsFixed(2)}×',
        (v) => draft.resourceRegeneration = v,
        divisions: 60,
      ),
      _slider(
        '代謝コスト',
        draft.metabolism,
        .25,
        3,
        '${draft.metabolism.toStringAsFixed(2)}×',
        (v) => draft.metabolism = v,
        divisions: 55,
      ),
      _slider(
        '移動コスト',
        draft.movementCost,
        0,
        3,
        '${draft.movementCost.toStringAsFixed(2)}×',
        (v) => draft.movementCost = v,
        divisions: 60,
      ),
      _tile(
        '子の突然変異',
        'OFF は固定ゲノムの対照実験',
        Switch(
          value: draft.mutation,
          onChanged: (v) => _change(() => draft.mutation = v),
        ),
      ),
      _tile(
        'デトリタス',
        '寿命で死んだ個体の残りエネルギーを餌に',
        Switch(
          value: draft.detritus,
          onChanged: (v) => _change(() => draft.detritus = v),
        ),
      ),
      _tile(
        'フォルダを餌に',
        'サブフォルダも含む最大20件。各ファイルの先頭1 MBを使用',
        Switch(
          value: draft.useFood && files.isNotEmpty,
          onChanged: files.isEmpty
              ? null
              : (v) => _change(() => draft.useFood = v),
        ),
      ),
      OutlinedButton.icon(
        onPressed: loading ? null : _pickFolder,
        icon: const Icon(Icons.folder_open),
        label: Text(loading ? '読み込み中…' : '餌のフォルダを選択'),
      ),
      if (foodFolderName != null)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text('$foodFolderName  •  ${files.length}件のファイル'),
        ),
      if (files.isNotEmpty)
        Text(
          files.map((f) => f.name).join('、'),
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
        ),
      _slider(
        'ファイル餌の一斉復活',
        draft.regrowInterval.toDouble(),
        0,
        500,
        draft.regrowInterval == 0 ? 'OFF' : '${draft.regrowInterval} tick',
        (v) => draft.regrowInterval = v.round(),
        divisions: 100,
      ),
      const SizedBox(height: 12),
      Text(
        '一斉復活はファイルの餌にだけ適用されます。餌の量と周期を変えて結果を比べてください。',
        style: Theme.of(context).textTheme.bodySmall,
      ),
    ],
  );

  Widget _results() => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      const Text(
        '実験結果',
        style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 8),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            children: [
              _stat('現在の個体数', '${sim.life.length}'),
              _stat('誕生 / 死亡', '${sim.births} / ${sim.deaths}'),
              _stat('最大世代', '${sim.maxGeneration}'),
              _stat('残りのファイル餌', sim.foodEnergy.toStringAsFixed(1)),
              _stat('直近の摂食', sim.eaten.toStringAsFixed(1)),
            ],
          ),
        ),
      ),
      const SizedBox(height: 8),
      const Text('個体数の推移', style: TextStyle(fontWeight: FontWeight.bold)),
      SizedBox(
        height: 150,
        child: Card(
          child: CustomPaint(
            painter: HistoryPainter(sim.populationHistory),
            child: const SizedBox.expand(),
          ),
        ),
      ),
      const SizedBox(height: 8),
      const Text('遺伝子の平均', style: TextStyle(fontWeight: FontWeight.bold)),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            children: [
              for (var i = 0; i < geneNames.length; i++)
                _stat(
                  geneNames[i],
                  sim
                      .meanGene(i)
                      .toStringAsFixed(i == 3 || i == 4 || i == 7 ? 3 : 2),
                ),
            ],
          ),
        ),
      ),
      const SizedBox(height: 8),
      FilledButton.icon(
        onPressed: _share,
        icon: const Icon(Icons.ios_share),
        label: const Text('条件と結果を共有 (JSON)'),
      ),
      const SizedBox(height: 12),
      Text(
        'このアプリのエンジンは Dart 製のモバイルモデルです。Python 版と同じ基礎ルールを使いますが、乱数と演算順が異なり、simulation contract 2 のビット単位の再現性はありません。厳密な比較には Python 版を使用してください。',
        style: Theme.of(context).textTheme.bodySmall,
      ),
    ],
  );

  Widget _stat(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(
      children: [
        Expanded(child: Text(label)),
        Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Row(
        children: [
          ClipRRect(
            borderRadius: BorderRadius.circular(7),
            child: Image.asset(
              'assets/brand/eyggdranex-mark.png',
              width: 30,
              height: 30,
            ),
          ),
          const SizedBox(width: 9),
          const Text('EYGGDRANEX'),
        ],
      ),
      centerTitle: false,
      actions: [
        if (playing)
          const Padding(
            padding: EdgeInsets.only(right: 14),
            child: Icon(Icons.circle, color: Color(0xff79e2a5), size: 12),
          ),
      ],
    ),
    body: IndexedStack(index: tab, children: [_world(), _rules(), _results()]),
    bottomNavigationBar: NavigationBar(
      selectedIndex: tab,
      onDestinationSelected: (i) => setState(() => tab = i),
      destinations: const [
        NavigationDestination(icon: Icon(Icons.public), label: '世界'),
        NavigationDestination(icon: Icon(Icons.tune), label: 'ルール'),
        NavigationDestination(icon: Icon(Icons.show_chart), label: '結果'),
      ],
    ),
  );
}

class WorldPainter extends CustomPainter {
  final MobileSimulation sim;
  WorldPainter(this.sim);
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(
      Offset.zero & size,
      Paint()..color = const Color(0xff0a1b21),
    );
    final grid = Paint()
      ..color = const Color(0xff19313a)
      ..strokeWidth = .5;
    for (var i = 1; i < 10; i++) {
      final p = size.width * i / 10;
      canvas.drawLine(Offset(p, 0), Offset(p, size.height), grid);
      canvas.drawLine(
        Offset(0, size.height * i / 10),
        Offset(size.width, size.height * i / 10),
        grid,
      );
    }
    for (final p in sim.patches) {
      final paint = Paint()
        ..color = p.food
            ? const Color(0xffffbc69)
            : p.regen < 0
            ? const Color(0xffae89d9)
            : const Color(0xff54a9cf);
      final radius = (1.8 + sqrt(max(0, p.energy)) * .55).clamp(1.8, 8.0);
      canvas.drawCircle(
        Offset(p.x / 100 * size.width, p.y / 100 * size.height),
        radius,
        paint,
      );
    }
    final dot = Paint()..color = const Color(0xff79e2a5);
    for (final o in sim.life) {
      canvas.drawCircle(
        Offset(o.x / 100 * size.width, o.y / 100 * size.height),
        2.0,
        dot,
      );
    }
  }

  @override
  bool shouldRepaint(covariant WorldPainter oldDelegate) => true;
}

class HistoryPainter extends CustomPainter {
  final List<int> values;
  HistoryPainter(this.values);
  @override
  void paint(Canvas canvas, Size size) {
    if (values.length < 2) return;
    final maxValue = max(1, values.reduce(max));
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final x = i / (values.length - 1) * size.width;
      final y = size.height - values[i] / maxValue * (size.height - 12) - 6;
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = const Color(0xff79e2a5)
        ..strokeWidth = 2
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant HistoryPainter oldDelegate) => true;
}
