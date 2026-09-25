# EYGGDRANEX

**Japanese reading:** エグドラネクス  
**Short technical identifier:** `EYGGNX`

### Open-Ended Artificial Digital Life Ecosystem

**Repository:** https://github.com/ghasindusk/EYGGDRANEX  
**Author:** SHAR-K

> **かつて憧れたデジタル生命の世界は、もうフィクションではない。**  
> **今度は俺たちが、それを現実にする。**  
> **そして、その先へ。**
>
> *The worlds we once dreamed of are no longer fiction.  
> Now, we can build beyond them.*

**EYGGDRANEX（エグドラネクス、略称 EYGGNX）**は、あらかじめ種・進化ツリー・敵・最適解を定義せず、低レベルの生命則と環境則からデジタル生命と生態系の創発を目指すオープンエンド型A-Lifeプロジェクトです。

> **We do not design life. We design the conditions from which life can emerge.**

## Naming

- **Formal project/brand:** EYGGDRANEX
- **Japanese reading:** エグドラネクス
- **Technical short form:** EYGGNX
- **Python distribution / CLI:** `eyggnx`

`EYGGNX` is the preferred compact technical identifier. Public-facing releases and research citations should retain the full **EYGGDRANEX** name.

## v0.1.1-alpha — GENESIS Review Integration

v0.1.1-alpha は、公開済み v0.1.0-alpha を基準点として Astra / Opus の独立監査を統合した品質・再現性強化版です。simulation contract 1 を維持しつつ、実験設定、run record、lineage/時系列記録、対照条件、入力検証、golden digest、package CI を追加しています。

`Genome → Metabolism → Perception → Action → Energy → Reproduction → Mutation → Death → Selection`

現在の最小実装には以下が含まれます。

- 遺伝パラメータを持つデジタル個体
- エネルギー代謝と移動コスト
- 資源知覚と採餌
- 無性生殖と遺伝子突然変異
- 年齢・エネルギーによる死
- 2Dトーラス世界と資源再生
- Seed固定による再現可能な実験
- 設定ファイル・run record・時系列/系統ログ
- 中立ドリフト / 固定ゲノム対照
- platform別 golden digest と wheel/package CI

### Current limitations

- 行動則は固定の資源指向制御器で、遺伝しない。進化するのは生理・生活史パラメータだけである。
- 個体はリスト順に行動する。この順序は進化する生活史戦略に強く影響する（`docs/specifications/ORGANISM_SPEC.md`）。
- 対価のない遺伝子は、長期的に clamp 境界へ移動する（`docs/specifications/GENOME_SPEC.md`）。
- golden digest はplatformごとに管理する。現時点でOSをまたいだbit-identical trajectoryは主張しない。
- GENESIS の結果は「創発の実証」ではなく、計測可能な基準系として扱う。

## What EYGGDRANEX defines / does not define

**Defines:** information, energy, perception, metabolism, reproduction, mutation, environmental constraints and computation.

**Does not predefine:** species, fixed evolution trees, enemies, quests, optimal strategies or final forms.

ルールは結果を決めるためではなく、**可能性の境界を与えるため**に存在します。

## Quick start

```bash
eyggnx --steps 200 --seed 42
```

開発環境から実行する場合:

```bash
python -m pip install -e .
eyggnx --steps 200 --seed 42
python -m unittest discover -s tests -v
```

再現可能な実験記録を残す場合:

```bash
eyggnx --config configs/default_genesis.json --format record --record-dir runs/demo > runs/demo.json
```

詳細は [`EXPERIMENT_PROTOCOL.md`](EXPERIMENT_PROTOCOL.md) を参照してください。

## Repository map

- `src/eyggnx/` — GENESIS最小エンジン
- `docs/specifications/` — Genome / Organism / Evolution / Ecosystem仕様
- `docs/architecture/` — システム構造
- `docs/research/` — 創発判定と実験原則
- `experiments/genesis/` — 再現可能な実験記録
- `.github/` — CI / Issue / PR設定

## Roadmap

- **Genesis** — 最小生命ループ
- **Ecology** — 捕食・共生・寄生・ニッチ
- **Cognition** — 学習・記憶・内発的動機
- **Culture** — 社会・情報継承・技術進化
- **Embodiment** — プロシージャル形態・3D世界
- **Open World** — 外部データ流・分散生命圏

詳細は [`ROADMAP.md`](ROADMAP.md) を参照してください。

## Author

**SHAR-K**

Security reports should follow [`SECURITY.md`](SECURITY.md).

## Licensing

- **Source code:** Mozilla Public License 2.0 (`MPL-2.0`)
- **Project documentation:** CC BY-SA 4.0
- **EYGGDRANEX name / future official logos / official brand assets:** ライセンス対象外。

詳細は [`CONTENT_LICENSE.md`](CONTENT_LICENSE.md) と [`TRADEMARKS.md`](TRADEMARKS.md) を参照してください。

## Status

**v0.1.1-alpha — experimental.** 研究・実験用途を想定した初期段階であり、API互換性・生態系安定性・長期保存形式は保証されません。
