// Copyright (c) 2026 SHAR-K. MPL-2.0.
import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:share_plus/share_plus.dart';

import 'background_run.dart';
import 'simulation.dart';

void main() => runApp(const EyggdranexApp());

/// Colors of the four things in the world, shared by the map, legend and results.
const lifeColor = Color(0xff79e2a5);
const renewableColor = Color(0xff54a9cf);
const fileFoodColor = Color(0xffffbc69);
const detritusColor = Color(0xffae89d9);

enum Layer { life, renewable, fileFood, detritus }

class EyggdranexApp extends StatelessWidget {
  const EyggdranexApp({
    super.key,
    this.backgroundRunner = const BackgroundRunController(),
  });

  final BackgroundRunController backgroundRunner;
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'EYGGDRANEX',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: lifeColor,
        brightness: Brightness.dark,
      ),
      scaffoldBackgroundColor: const Color(0xff0b1417),
      cardTheme: CardThemeData(
        color: const Color(0xff12252a),
        elevation: 0,
        margin: const EdgeInsets.symmetric(vertical: 4),
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
    home: LabPage(backgroundRunner: backgroundRunner),
  );
}

class LabPage extends StatefulWidget {
  const LabPage({super.key, required this.backgroundRunner});

  final BackgroundRunController backgroundRunner;
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
  Future<void>? backgroundStopping;
  bool playing = false, starting = false, visible = true;
  bool dirty = false, loading = false;
  int tab = 0, ticksPerFrame = 1;
  String? error;
  BackgroundStatus status = const BackgroundStatus();
  final Set<Layer> hidden = {};
  bool colorByLineage = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    sim = MobileSimulation(draft, files);
    unawaited(_refreshStatus());
  }

  @override
  void dispose() {
    timer?.cancel();
    if (playing) unawaited(widget.backgroundRunner.stop());
    WidgetsBinding.instance.removeObserver(this);
    seedController.dispose();
    super.dispose();
  }

  Future<void> _refreshStatus() async {
    try {
      final next = await widget.backgroundRunner.status();
      if (mounted) setState(() => status = next);
    } catch (_) {
      // Status is informational only.
    }
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    visible = state == AppLifecycleState.resumed;
    if (visible && mounted) {
      setState(() {});
      unawaited(_refreshStatus());
    }
  }

  void _pause() {
    timer?.cancel();
    timer = null;
    if (playing) {
      backgroundStopping = widget.backgroundRunner.stop().catchError((
        Object e,
      ) {
        if (mounted) setState(() => error = 'バックグラウンド実行の停止に失敗しました: $e');
      });
    }
    if (mounted) setState(() => playing = false);
  }

  Future<void> _play() async {
    if (playing) {
      _pause();
      return;
    }
    if (starting) return;
    if (sim.life.isEmpty) _reset();
    if (sim.life.isEmpty) return;
    setState(() {
      starting = true;
      error = null;
    });
    try {
      await backgroundStopping;
      final ready = await widget.backgroundRunner.start();
      if (!mounted) {
        if (ready) await widget.backgroundRunner.stop();
        return;
      }
      if (!ready) throw StateError('Android の実行サービスを開始できませんでした');
      setState(() => playing = true);
      timer = Timer.periodic(const Duration(milliseconds: 50), _onFrame);
      unawaited(_refreshStatus());
    } catch (e) {
      if (mounted) setState(() => error = 'バックグラウンド実行を開始できませんでした: $e');
    } finally {
      if (mounted) setState(() => starting = false);
    }
  }

  void _onFrame(Timer _) {
    if (!mounted) return;
    try {
      // Yield after every small batch so controls stay responsive on a phone.
      for (var i = 0; i < ticksPerFrame && sim.life.isNotEmpty; i++) {
        sim.tick();
      }
      if (sim.life.isEmpty) {
        _pause();
      }
      if (visible) setState(() {});
    } catch (e) {
      _pause();
      setState(() {
        error = '$e';
      });
    }
  }

  void _reset() {
    if (starting) return;
    _pause();
    final seed = int.tryParse(seedController.text.trim());
    if (seed == null) {
      setState(() {
        error = 'シードには整数を入力してください';
      });
      return;
    }
    setState(() {
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
    if (playing) _pause();
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
    'appVersion': status.version,
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
    'eaten': {
      'renewable': sim.eatenRenewable,
      'file': sim.eatenFile,
      'detritus': sim.eatenDetritus,
    },
    'founderMeanGenes': {
      for (var i = 0; i < geneNames.length; i++)
        geneNames[i]: sim.founderMeans[i],
    },
    'meanGenes': {
      for (var i = 0; i < geneNames.length; i++) geneNames[i]: sim.meanGene(i),
    },
    'mutation': {
      'mutatedBirths': sim.mutatedBirths,
      'largeMutations': sim.largeMutations,
      'meanSizePerGene': {
        for (var i = 0; i < geneNames.length; i++)
          geneNames[i]: sim.meanMutation(i),
      },
    },
    'lineages': [
      for (final e in sim.lineages().take(10))
        {'founder': e.key, 'living': e.value},
    ],
    'historyTicks': sim.historyTicks,
    'populationHistory': sim.populationHistory,
    'generationHistory': sim.generationHistory,
    'geneHistory': sim.geneHistory,
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

  // ---------------------------------------------------------------- widgets

  TextStyle? get _small => Theme.of(context).textTheme.bodySmall;

  Widget _heading(String text) => Padding(
    padding: const EdgeInsets.fromLTRB(4, 14, 4, 4),
    child: Text(
      text,
      style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
    ),
  );

  Widget _section(
    IconData icon,
    Color color,
    String title,
    String description,
    List<Widget> children,
  ) => Padding(
    padding: const EdgeInsets.only(top: 14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(width: 8),
            Text(
              title,
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
            ),
          ],
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(28, 2, 0, 6),
          child: Text(description, style: _small),
        ),
        ...children,
      ],
    ),
  );

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
                Text(subtitle, style: _small),
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
    String? help,
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
          if (help != null) Text(help, style: _small),
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

  Widget _metric(String name, String value, {Color? color}) => Card(
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
      child: Column(
        children: [
          FittedBox(
            child: Text(
              value,
              style: TextStyle(
                fontSize: 22,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ),
          Text(name, style: Theme.of(context).textTheme.labelSmall),
        ],
      ),
    ),
  );

  Widget _stat(String label, String value, {Color? color}) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 5),
    child: Row(
      children: [
        Expanded(child: Text(label)),
        Text(
          value,
          style: TextStyle(fontWeight: FontWeight.w600, color: color),
        ),
      ],
    ),
  );

  // ------------------------------------------------------------------ world

  Widget _banner() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      if (dirty)
        Card(
          color: const Color(0xff51411f),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(14, 4, 4, 4),
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
        padding: const EdgeInsets.all(12),
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
              borderRadius: BorderRadius.circular(14),
              child: Image.asset(
                'assets/brand/eyggdranex-mark.png',
                width: 52,
                height: 52,
              ),
            ),
            const SizedBox(width: 12),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '世界を観察する',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(height: 2),
                  Text('種から始まる、手のひらの生態系。'),
                ],
              ),
            ),
          ],
        ),
      ),
    ],
  );

  Widget _backgroundNotice() {
    if (!playing) return const SizedBox.shrink();
    if (!status.notificationsEnabled) {
      return Card(
        color: const Color(0xff3d3520),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(14, 8, 6, 8),
          child: Row(
            children: [
              const Icon(Icons.notifications_off_outlined, size: 20),
              const SizedBox(width: 10),
              const Expanded(
                child: Text('通知がオフのため、実行中の通知は表示されません。バックグラウンドでの進行は続きます。'),
              ),
              TextButton(
                onPressed: () => unawaited(
                  widget.backgroundRunner.openNotificationSettings(),
                ),
                child: const Text('通知を許可'),
              ),
            ],
          ),
        ),
      );
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          const Icon(Icons.play_circle_outline, size: 18, color: lifeColor),
          const SizedBox(width: 6),
          Expanded(child: Text('バックグラウンドでも進行中 • 通知からアプリに戻れます', style: _small)),
        ],
      ),
    );
  }

  Widget _legendChip(Layer layer, Color color, String label, String value) {
    final shown = !hidden.contains(layer);
    return FilterChip(
      selected: shown,
      showCheckmark: false,
      avatar: SizedBox(
        width: 18,
        height: 18,
        child: CustomPaint(painter: GlyphPainter(layer, color, dim: !shown)),
      ),
      label: Text('$label  $value'),
      onSelected: (v) => setState(() {
        if (v) {
          hidden.remove(layer);
        } else {
          hidden.add(layer);
        }
      }),
    );
  }

  Widget _layerSummary() {
    final fileTotal = sim.fileFoodTotal;
    final regrow = sim.ticksToRegrow;
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
        child: Column(
          children: [
            _layerRow(
              Layer.life,
              lifeColor,
              '個体',
              '餌を食べて動き、エネルギーがたまると子を産む',
              '${sim.life.length} 体',
            ),
            _layerRow(
              Layer.renewable,
              renewableColor,
              '再生する餌',
              '世界にもとからある餌。食べても少しずつ回復する',
              '${sim.renewableCount} か所 • ${sim.renewableEnergy.toStringAsFixed(0)}',
            ),
            if (sim.foodTemplates.isNotEmpty)
              _layerRow(
                Layer.fileFood,
                fileFoodColor,
                'ファイルの餌',
                regrow == null
                    ? '選んだファイルから作った餌。ゆっくり出てきて、食べ尽くすと消える'
                    : '選んだファイルから作った餌。$regrow tick 後に全部が元に戻る',
                '${sim.fileFoodCount}/${sim.foodTemplates.length} • '
                    '${fileTotal <= 0 ? 0 : (sim.foodEnergy / fileTotal * 100).round()}%',
              ),
            if (sim.detritusCount > 0)
              _layerRow(
                Layer.detritus,
                detritusColor,
                'デトリタス',
                '死んだ個体が残した餌。だんだん減って消える',
                '${sim.detritusCount} か所',
              ),
          ],
        ),
      ),
    );
  }

  Widget _layerRow(
    Layer layer,
    Color color,
    String title,
    String help,
    String value,
  ) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 4),
    child: Row(
      children: [
        SizedBox(
          width: 22,
          height: 22,
          child: CustomPaint(painter: GlyphPainter(layer, color)),
        ),
        const SizedBox(width: 10),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
              Text(help, style: _small),
            ],
          ),
        ),
        const SizedBox(width: 8),
        Text(
          value,
          style: TextStyle(color: color, fontWeight: FontWeight.w700),
        ),
      ],
    ),
  );

  Widget _world() => ListView(
    key: const Key('world-list'),
    padding: const EdgeInsets.all(14),
    children: [
      _banner(),
      const SizedBox(height: 8),
      AspectRatio(
        aspectRatio: 1,
        child: Card(
          clipBehavior: Clip.antiAlias,
          child: CustomPaint(
            painter: WorldPainter(
              sim,
              hidden: hidden,
              colorByLineage: colorByLineage,
            ),
            child: const SizedBox.expand(),
          ),
        ),
      ),
      const SizedBox(height: 6),
      Wrap(
        spacing: 6,
        runSpacing: 2,
        children: [
          _legendChip(Layer.life, lifeColor, '個体', '${sim.life.length}'),
          _legendChip(
            Layer.renewable,
            renewableColor,
            '再生する餌',
            '${sim.renewableCount}',
          ),
          if (sim.foodTemplates.isNotEmpty)
            _legendChip(
              Layer.fileFood,
              fileFoodColor,
              'ファイルの餌',
              '${sim.fileFoodCount}',
            ),
          if (sim.rules.detritus)
            _legendChip(
              Layer.detritus,
              detritusColor,
              'デトリタス',
              '${sim.detritusCount}',
            ),
          FilterChip(
            selected: colorByLineage,
            avatar: const Icon(Icons.palette_outlined, size: 18),
            label: const Text('系統で色分け'),
            onSelected: (v) => setState(() => colorByLineage = v),
          ),
        ],
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(child: _metric('TICK', '${sim.tickIndex}')),
          Expanded(
            child: _metric('個体', '${sim.life.length}', color: lifeColor),
          ),
          Expanded(child: _metric('最大世代', '${sim.maxGeneration}')),
        ],
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            child: FilledButton.icon(
              onPressed: starting ? null : _play,
              icon: Icon(playing ? Icons.pause : Icons.play_arrow),
              label: Text(
                starting
                    ? '起動中…'
                    : playing
                    ? '一時停止'
                    : '開始',
              ),
            ),
          ),
          const SizedBox(width: 8),
          OutlinedButton.icon(
            onPressed: starting ? null : _reset,
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
      const SizedBox(height: 6),
      _backgroundNotice(),
      if (sim.life.isEmpty)
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 4),
          child: Text('個体群が絶滅しました。ルールを変えて再実行できます。'),
        ),
      _heading('世界にあるもの'),
      _layerSummary(),
    ],
  );

  // ------------------------------------------------------------------ rules

  Widget _rules() => ListView(
    key: const Key('rules-list'),
    padding: const EdgeInsets.all(14),
    children: [
      const Text(
        'ルールを組み立てる',
        style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 4),
      Text('初期値がバニラです。変更は「反映してリセット」で新しい世界に適用します。', style: _small),
      const SizedBox(height: 12),
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
      _section(Icons.circle, lifeColor, '個体', '最初に置く個体と、子が親からどう変わるか。', [
        TextField(
          controller: seedController,
          keyboardType: const TextInputType.numberWithOptions(signed: true),
          decoration: const InputDecoration(
            labelText: 'シード',
            border: OutlineInputBorder(),
            helperText: '同じ設定とシードならモバイル版で同じ結果を再現できます',
          ),
          onChanged: (_) => setState(() => dirty = true),
        ),
        const SizedBox(height: 6),
        _slider(
          '創始個体',
          draft.founders.toDouble(),
          0,
          200,
          '${draft.founders}',
          (v) => draft.founders = v.round(),
          divisions: 200,
        ),
        _tile(
          '子の突然変異',
          'OFF にすると子は親と同じ遺伝子になる（進化しない対照実験）',
          Switch(
            value: draft.mutation,
            onChanged: (v) => _change(() => draft.mutation = v),
          ),
        ),
        _slider(
          '代謝コスト',
          draft.metabolism,
          .25,
          3,
          '${draft.metabolism.toStringAsFixed(2)}×',
          (v) => draft.metabolism = v,
          divisions: 55,
          help: '生きているだけで毎 tick 減るエネルギー',
        ),
        _slider(
          '移動コスト',
          draft.movementCost,
          0,
          3,
          '${draft.movementCost.toStringAsFixed(2)}×',
          (v) => draft.movementCost = v,
          divisions: 60,
          help: '動いた距離と速さに応じて減るエネルギー',
        ),
      ]),
      _section(
        Icons.water_drop,
        renewableColor,
        '再生する餌',
        '世界にもとからある餌。食べられても少しずつ回復する。',
        [
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
            help: '0 にすると回復しない（食べ尽くすと終わり）',
          ),
        ],
      ),
      _section(
        Icons.description,
        fileFoodColor,
        'ファイルの餌',
        'スマホのフォルダから作る餌。中身の情報量（圧縮後の大きさ）がエネルギーになり、少しずつ出てくる。ファイルは読むだけで実行しない。',
        [
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
              style: _small,
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
          _slider(
            'ファイル餌の一斉復活',
            draft.regrowInterval.toDouble(),
            0,
            500,
            draft.regrowInterval == 0 ? 'OFF' : '${draft.regrowInterval} tick',
            (v) => draft.regrowInterval = v.round(),
            divisions: 100,
            help: 'この間隔ごとにファイルの餌が全部元に戻る（再生する餌には影響しない）',
          ),
        ],
      ),
      _section(Icons.change_history, detritusColor, 'デトリタス', '死んだ個体が残す餌。', [
        _tile(
          'デトリタスを残す',
          '寿命で死んだ個体の残りエネルギーの半分を餌にする',
          Switch(
            value: draft.detritus,
            onChanged: (v) => _change(() => draft.detritus = v),
          ),
        ),
      ]),
      const SizedBox(height: 20),
    ],
  );

  // ---------------------------------------------------------------- results

  String _fmtGene(int i, double v) =>
      v.toStringAsFixed(i == 3 || i == 4 || i == 7 ? 3 : (v >= 100 ? 0 : 2));

  Widget _geneCard(int i) {
    final start = sim.founderMeans[i], now = sim.meanGene(i);
    final ratio = start > 0 && sim.life.isNotEmpty ? now / start : 1.0;
    final up = ratio > 1.05, down = ratio < 1 / 1.05;
    final color = up
        ? lifeColor
        : down
        ? const Color(0xffff8a80)
        : Theme.of(context).colorScheme.onSurfaceVariant;
    final (lo, hi) = sim.geneRange(i);
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    geneNames[i],
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                Icon(
                  up
                      ? Icons.trending_up
                      : down
                      ? Icons.trending_down
                      : Icons.trending_flat,
                  color: color,
                  size: 18,
                ),
                const SizedBox(width: 4),
                Text(
                  '×${ratio.toStringAsFixed(2)}',
                  style: TextStyle(color: color, fontWeight: FontWeight.w700),
                ),
              ],
            ),
            Text(geneHelp[i], style: _small),
            const SizedBox(height: 6),
            Row(
              children: [
                Text(
                  '開始 ${_fmtGene(i, start)} → 現在 ${_fmtGene(i, now)}',
                  style: _small,
                ),
                const Spacer(),
                Text(
                  '変異の大きさ ${(sim.meanMutation(i) * 100).toStringAsFixed(1)}%',
                  style: _small,
                ),
              ],
            ),
            const SizedBox(height: 6),
            SizedBox(
              height: 34,
              child: CustomPaint(
                painter: SparklinePainter(
                  [for (final g in sim.geneHistory) g[i]],
                  color: color,
                  baseline: start,
                ),
                child: const SizedBox.expand(),
              ),
            ),
            const SizedBox(height: 4),
            SizedBox(
              height: 16,
              child: CustomPaint(
                painter: RangePainter(
                  lower: geneLower[i],
                  upper: geneUpper[i],
                  min: lo,
                  max: hi,
                  mean: now,
                  start: start,
                ),
                child: const SizedBox.expand(),
              ),
            ),
            Row(
              children: [
                Text(_fmtGene(i, geneLower[i]), style: _small),
                const Spacer(),
                if (sim.life.isNotEmpty)
                  Text(
                    '個体の範囲 ${_fmtGene(i, lo)}〜${_fmtGene(i, hi)}',
                    style: _small,
                  ),
                const Spacer(),
                Text(_fmtGene(i, geneUpper[i]), style: _small),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _mutationCard() {
    final events = sim.recentMutations.reversed.take(8).toList();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _stat('変異した誕生', '${sim.mutatedBirths} / ${sim.births}'),
            _stat('大きな変異（どれかの遺伝子が約10%以上）', '${sim.largeMutations}'),
            if (!sim.rules.mutation)
              Text('子の突然変異は OFF です（固定ゲノムの対照実験）', style: _small),
            if (events.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('最近の大きな変異', style: _small),
              for (final e in events)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 3),
                  child: Row(
                    children: [
                      Icon(
                        e.ratio >= 1
                            ? Icons.arrow_upward
                            : Icons.arrow_downward,
                        size: 14,
                        color: e.ratio >= 1
                            ? lifeColor
                            : const Color(0xffff8a80),
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          '${geneNames[e.gene]} ×${e.ratio.toStringAsFixed(2)}'
                          '  •  第${e.generation}世代 #${e.childId}（親 #${e.parentId}）',
                        ),
                      ),
                      Text('t${e.tick}', style: _small),
                    ],
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _lineageCard() {
    final lineages = sim.lineages();
    final total = max(1, sim.life.length);
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _stat('生き残っている系統', '${lineages.length} / ${sim.rules.founders}'),
            Text('系統 = 同じ創始個体から続く子孫', style: _small),
            const SizedBox(height: 6),
            for (final e in lineages.take(5))
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        color: lineageColor(e.key),
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    SizedBox(width: 70, child: Text('系統 #${e.key}')),
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          value: e.value / total,
                          minHeight: 8,
                          color: lineageColor(e.key),
                          backgroundColor: const Color(0xff1d353b),
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Text('${e.value}体 ${(e.value / total * 100).round()}%'),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _foodCard() {
    final total = sim.eatenRenewable + sim.eatenFile + sim.eatenDetritus;
    Widget part(double value, Color color) => Expanded(
      flex: total <= 0 ? 1 : max(1, (value / total * 1000).round()),
      child: Container(height: 10, color: color),
    );
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (total > 0)
              ClipRRect(
                borderRadius: BorderRadius.circular(5),
                child: Row(
                  children: [
                    if (sim.eatenRenewable > 0)
                      part(sim.eatenRenewable, renewableColor),
                    if (sim.eatenFile > 0) part(sim.eatenFile, fileFoodColor),
                    if (sim.eatenDetritus > 0)
                      part(sim.eatenDetritus, detritusColor),
                  ],
                ),
              ),
            const SizedBox(height: 6),
            _stat(
              '再生する餌から',
              sim.eatenRenewable.toStringAsFixed(0),
              color: renewableColor,
            ),
            _stat(
              'ファイルの餌から',
              sim.eatenFile.toStringAsFixed(0),
              color: fileFoodColor,
            ),
            if (sim.rules.detritus)
              _stat(
                'デトリタスから',
                sim.eatenDetritus.toStringAsFixed(0),
                color: detritusColor,
              ),
            if (sim.foodTemplates.isNotEmpty)
              _stat(
                '残りのファイル餌',
                '${sim.foodEnergy.toStringAsFixed(0)} / ${sim.fileFoodTotal.toStringAsFixed(0)}',
              ),
          ],
        ),
      ),
    );
  }

  Widget _results() => ListView(
    key: const Key('results-list'),
    padding: const EdgeInsets.all(14),
    children: [
      const Text(
        '実験結果',
        style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold),
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(child: _metric('TICK', '${sim.tickIndex}')),
          Expanded(
            child: _metric('個体', '${sim.life.length}', color: lifeColor),
          ),
          Expanded(child: _metric('最大世代', '${sim.maxGeneration}')),
        ],
      ),
      Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            children: [
              _stat('誕生 / 死亡', '${sim.births} / ${sim.deaths}'),
              _stat('直近の摂食', sim.eaten.toStringAsFixed(1)),
            ],
          ),
        ),
      ),
      _heading('個体数と世代の推移'),
      Card(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
          child: Column(
            children: [
              SizedBox(
                height: 150,
                child: CustomPaint(
                  painter: HistoryPainter(
                    sim.populationHistory,
                    sim.generationHistory,
                  ),
                  child: const SizedBox.expand(),
                ),
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  _swatch(
                    lifeColor,
                    '個体数（最大 ${sim.populationHistory.fold(0, max)}）',
                  ),
                  const SizedBox(width: 14),
                  _swatch(Colors.white70, '最大世代'),
                  const Spacer(),
                  if (sim.historyTicks.isNotEmpty)
                    Text('0〜${sim.historyTicks.last} tick', style: _small),
                ],
              ),
            ],
          ),
        ),
      ),
      _heading('遺伝子の変化'),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 4),
        child: Text(
          '創始個体の平均と比べた現在の平均。線は時間ごとの平均（点線は開始時）、下の帯は今いる個体の範囲（濃い縦線が平均、白い印が開始時）。',
          style: _small,
        ),
      ),
      for (var i = 0; i < geneNames.length; i++) _geneCard(i),
      _heading('突然変異'),
      _mutationCard(),
      _heading('系統'),
      _lineageCard(),
      _heading('食べた餌'),
      _foodCard(),
      const SizedBox(height: 10),
      FilledButton.icon(
        onPressed: _share,
        icon: const Icon(Icons.ios_share),
        label: const Text('条件と結果を共有 (JSON)'),
      ),
      const SizedBox(height: 12),
      Text(
        'このアプリのエンジンは Dart 製のモバイルモデルです。Python 版と同じ基礎ルールを使いますが、乱数と演算順が異なり、simulation contract 2 のビット単位の再現性はありません。厳密な比較には Python 版を使用してください。',
        style: _small,
      ),
      if (status.version.isNotEmpty)
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Text('アプリのバージョン ${status.version}', style: _small),
        ),
      const SizedBox(height: 12),
    ],
  );

  Widget _swatch(Color color, String label) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(width: 14, height: 3, color: color),
      const SizedBox(width: 5),
      Text(label, style: _small),
    ],
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
            child: Icon(Icons.circle, color: lifeColor, size: 12),
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

/// A stable, well-spread color for each founder lineage.
Color lineageColor(int lineage) =>
    HSVColor.fromAHSV(1, (lineage * 137.508) % 360, .55, .95).toColor();

/// Draws one map symbol: circle (individual), drop-like circle with ring
/// (renewable food), diamond (file food) or triangle (detritus).
void drawGlyph(
  Canvas canvas,
  Layer layer,
  Offset c,
  double r,
  Color color, {
  double fill = 1,
}) {
  switch (layer) {
    case Layer.life:
      canvas.drawCircle(c, r, Paint()..color = color);
      canvas.drawCircle(
        c,
        r,
        Paint()
          ..color = const Color(0xff0a1b21)
          ..style = PaintingStyle.stroke
          ..strokeWidth = .8,
      );
    case Layer.renewable:
      canvas.drawCircle(
        c,
        r,
        Paint()..color = color.withValues(alpha: .25 + .6 * fill),
      );
      canvas.drawCircle(
        c,
        r,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1,
      );
    case Layer.fileFood:
      final path = Path()
        ..moveTo(c.dx, c.dy - r)
        ..lineTo(c.dx + r, c.dy)
        ..lineTo(c.dx, c.dy + r)
        ..lineTo(c.dx - r, c.dy)
        ..close();
      canvas.drawPath(
        path,
        Paint()..color = color.withValues(alpha: .3 + .7 * fill),
      );
      canvas.drawPath(
        path,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2,
      );
    case Layer.detritus:
      final path = Path()
        ..moveTo(c.dx, c.dy - r)
        ..lineTo(c.dx + r * .9, c.dy + r * .7)
        ..lineTo(c.dx - r * .9, c.dy + r * .7)
        ..close();
      canvas.drawPath(path, Paint()..color = color);
  }
}

class GlyphPainter extends CustomPainter {
  final Layer layer;
  final Color color;
  final bool dim;
  GlyphPainter(this.layer, this.color, {this.dim = false});
  @override
  void paint(Canvas canvas, Size size) => drawGlyph(
    canvas,
    layer,
    size.center(Offset.zero),
    size.shortestSide * (layer == Layer.life ? .28 : .42),
    dim ? color.withValues(alpha: .35) : color,
    fill: .7,
  );

  @override
  bool shouldRepaint(covariant GlyphPainter old) =>
      old.layer != layer || old.color != color || old.dim != dim;
}

class WorldPainter extends CustomPainter {
  final MobileSimulation sim;
  final Set<Layer> hidden;
  final bool colorByLineage;
  WorldPainter(this.sim, {this.hidden = const {}, this.colorByLineage = false});
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
    final scale = size.width / 360;
    Offset at(double x, double y) =>
        Offset(x / 100 * size.width, y / 100 * size.height);
    for (final p in sim.patches) {
      final layer = p.food
          ? Layer.fileFood
          : p.regen < 0
          ? Layer.detritus
          : Layer.renewable;
      if (hidden.contains(layer)) continue;
      final fill = p.capacity > 0
          ? (p.energy / p.capacity).clamp(0.0, 1.0)
          : 0.0;
      final double r;
      final Color color;
      switch (layer) {
        case Layer.renewable:
          r = (2 + sqrt(max(0, p.capacity)) * .6) * scale;
          color = renewableColor;
        case Layer.fileFood:
          // Size shows what is left in total (exposed + reservoir).
          final left = p.energy + (p.reservoir ?? 0);
          r = (3.5 + sqrt(max(0, left)) * .18).clamp(3.5, 11.0) * scale;
          color = fileFoodColor;
        case Layer.detritus:
          r = 3.2 * scale;
          color = detritusColor;
        case Layer.life:
          continue;
      }
      drawGlyph(canvas, layer, at(p.x, p.y), r, color, fill: fill);
    }
    if (!hidden.contains(Layer.life)) {
      final r = 2.4 * scale;
      for (final o in sim.life) {
        drawGlyph(
          canvas,
          Layer.life,
          at(o.x, o.y),
          r,
          colorByLineage ? lineageColor(o.lineage) : lifeColor,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant WorldPainter oldDelegate) => true;
}

class HistoryPainter extends CustomPainter {
  final List<int> population;
  final List<int> generation;
  HistoryPainter(this.population, [this.generation = const []]);
  @override
  void paint(Canvas canvas, Size size) {
    final axis = Paint()
      ..color = const Color(0xff254147)
      ..strokeWidth = 1;
    canvas.drawLine(
      Offset(0, size.height - 1),
      Offset(size.width, size.height - 1),
      axis,
    );
    _line(canvas, size, generation, Colors.white70, 1.2);
    _line(canvas, size, population, lifeColor, 2);
  }

  void _line(
    Canvas canvas,
    Size size,
    List<int> values,
    Color color,
    double w,
  ) {
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
        ..color = color
        ..strokeWidth = w
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant HistoryPainter oldDelegate) => true;
}

/// Mean of one gene over time; the dotted line is the founders' mean.
class SparklinePainter extends CustomPainter {
  final List<double> values;
  final Color color;
  final double baseline;
  SparklinePainter(this.values, {required this.color, required this.baseline});
  @override
  void paint(Canvas canvas, Size size) {
    if (values.isEmpty) return;
    final lo = min(baseline, values.reduce(min));
    final hi = max(baseline, values.reduce(max));
    final span = hi - lo <= 0 ? 1.0 : hi - lo;
    double y(double v) => size.height - 3 - (v - lo) / span * (size.height - 6);
    final base = y(baseline);
    for (var x = 0.0; x < size.width; x += 6) {
      canvas.drawLine(
        Offset(x, base),
        Offset(min(size.width, x + 3), base),
        Paint()
          ..color = Colors.white38
          ..strokeWidth = 1,
      );
    }
    if (values.length < 2) return;
    final path = Path();
    for (var i = 0; i < values.length; i++) {
      final px = i / (values.length - 1) * size.width;
      if (i == 0) {
        path.moveTo(px, y(values[i]));
      } else {
        path.lineTo(px, y(values[i]));
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..strokeWidth = 1.8
        ..style = PaintingStyle.stroke,
    );
  }

  @override
  bool shouldRepaint(covariant SparklinePainter oldDelegate) => true;
}

/// Where the living population sits within a gene's bounds, on a log scale.
class RangePainter extends CustomPainter {
  final double lower, upper, min, max, mean, start;
  RangePainter({
    required this.lower,
    required this.upper,
    required this.min,
    required this.max,
    required this.mean,
    required this.start,
  });
  @override
  void paint(Canvas canvas, Size size) {
    double x(double v) {
      if (v <= 0) return 0;
      final t = (log(v) - log(lower)) / (log(upper) - log(lower));
      return t.clamp(0.0, 1.0) * size.width;
    }

    final mid = size.height / 2;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(0, mid - 3, size.width, 6),
        const Radius.circular(3),
      ),
      Paint()..color = const Color(0xff1d353b),
    );
    if (max > 0) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTRB(x(min), mid - 4, x(max) + 2, mid + 4),
          const Radius.circular(4),
        ),
        Paint()..color = lifeColor.withValues(alpha: .45),
      );
      canvas.drawLine(
        Offset(x(mean), 1),
        Offset(x(mean), size.height - 1),
        Paint()
          ..color = lifeColor
          ..strokeWidth = 2.5,
      );
    }
    final s = x(start);
    // Founders' mean: a small white marker above the bar.
    canvas.drawPath(
      Path()
        ..moveTo(s - 4, 0)
        ..lineTo(s + 4, 0)
        ..lineTo(s, 6)
        ..close(),
      Paint()..color = Colors.white70,
    );
  }

  @override
  bool shouldRepaint(covariant RangePainter oldDelegate) => true;
}
