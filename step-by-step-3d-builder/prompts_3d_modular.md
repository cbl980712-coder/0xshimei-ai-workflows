# 模块化 3D 提示词模板

用法：把下面三个模板按顺序、**一次只发一个**给任意大模型（Claude / ChatGPT / Gemini / Cursor 里的模型都行）。
`step_by_step_3d_builder.py prompt ...` 会把 `{{占位符}}` 自动填好，你直接复制输出即可；手动用也行。

为什么要拆：一句话让模型写完整 3D 场景，等于同时要求它定尺寸、定坐标、写几十个几何体、写交互、写动画——任何一处写错整页就白屏。
拆法：**先定"部件树 + 坐标 + 范围"（不写任何几何代码）→ 每次只写一个部件 → 每写一个就自检一次 → 最后才挂进场景。**

---

## 模板 1：拆解（部件树 + 坐标装配图）

<!-- template: decompose -->
```text
你是 3D 场景的"装配设计师"。现在只做拆解，禁止输出任何 Three.js 代码。

目标对象：{{description}}

{{source_block}}

请输出一个 JSON（只输出 JSON，不要解释），格式：
{
  "title": "页面标题",
  "subtitle": "一句话说明",
  "source_url": "{{source_url}}",
  "background": "#0b1020",
  "camera": {"position": [x, y, z], "target": [0, 0, 0]},
  "parts": [
    {
      "id": "英文小写下划线，唯一",
      "name": "中文名",
      "parent": "父部件 id；最外层部件填 null",
      "position": [x, y, z],        // 相对父部件的坐标，单位统一（整个场景最大尺寸约 8 个单位）
      "bound": 数字 或 [rx, ry, rz], // 这个部件以自身 position 为中心的最大半径（不是随便估，要能装下它）
      "inside": true,               // 可省略。true=必须在父部件 bound 内；"xz"=只要求水平投影在内；false=可以在外面
      "depends_on": ["必须先存在的其它部件 id"],
      "source_terms": ["在资料里能搜到的英文词，用来核对这个部件不是编的"],
      "desc": "一句话说明它是什么、起什么作用"
    }
  ]
}

硬性规则：
1. 部件数量 8～14 个，每个部件只负责一个可以独立点击的东西。
2. 子部件的 position 加上它自己的 bound，必须落在父部件 bound 之内（除非 inside=false）。写完自己心算检查一遍。
3. 同一个父部件下的兄弟部件，范围不要大幅重叠（会重叠的写 "allow_overlap": true 并说明原因）。
4. 每个部件的 source_terms 必须能在上面的资料里找到原词；资料里没有的部件不要加。
5. 最外层容器（外壳/底板）放第一个，它的 bound 要比所有内部件大。
6. 会运动的部件（活塞、摆轮、阀门……）：position 填运动行程的"中点"，bound 要包住整个行程，不是静止时的大小。
7. bound 用球太松时可写 [rx, ry, rz] 椭球；球/长方体的角会比你想的伸得更远，宁可留 10% 余量。
8. 长轴上的部件，bound 要把轴的长度算进去（轴从底板一直伸到齿轮层，就是那么长）。
```

---

## 模板 2：单个部件（循环使用，每个部件发一次）

<!-- template: part -->
```text
你是 Three.js 几何工程师。现在只写"一个"部件：{{part_name}}（id: {{part_id}}）。

整体对象：{{title}}
这个部件的任务：{{part_desc}}
它在装配图里的位置：相对父部件「{{parent_name}}」坐标 {{position}}，声明范围 bound = {{bound}}（部件所有顶点离自己原点不得超过它）
容器关系：{{inside_rule}}
已经写好、可以当参照的部件：{{done_parts}}

只输出这个部件的 JSON（不要解释，不要包含 position/bound，位置由装配图决定）：
{
  "shapes": [
    {"type": "sphere", "r": 1.2, "pos": [0,0,0], "color": "#7aa2ff", "opacity": 0.4},
    {"type": "scatter", "of": {"type":"sphere","r":0.06,"color":"#fff"}, "count": 40, "radius": [1.4, 2.0], "seed": 3, "exclude": [[x,y,z,r]], "orient": "radial"}
  ],
  "code": null,
  "anim": {"rotate": [0, 0.3, 0]},
  "update": null
}

可用 shapes：sphere{r} box{size:[x,y,z]} cylinder{r|rTop,rBottom,h} cone{r,h} torus{R,r,arc?} capsule{r,len}
tube{points:[[x,y,z],...],r} gear{module,teeth,thick,hole,axis} scatter{of,count,radius:[内,外],center?,seed,exclude?,minDist?,jitter?,orient?}。
通用字段：pos(相对本部件)、rot(角度)、scale、color、opacity、metal、rough、emissive。
需要循环/随机/复杂曲线时，用 "code"：一段函数体字符串，参数是 (THREE, ctx)，必须 return 一个 THREE.Object3D，
例如 "const g=new THREE.Group(); ... return g;"。ctx 里有 makeMat、makeGeo、rngFrom（带种子的随机数，不要用 Math.random）。
需要自定义运动时，"update" 是函数体字符串，参数 (node, t, ctx)，t 是秒；"anim" 只能做匀速旋转 rotate:[rx,ry,rz](弧度/秒) 和 oscillate:{mode:"move|rotate",axis,amp,speed,phase}。

约束：
- 不要使用 Math.random()、网络请求、外部纹理。
- 不要 import 任何东西，不要写 scene.add。
- 颜色用十六进制。半透明外壳 opacity ≤ 0.35，内部件用不透明。
- 只在 bound 范围内造型；宁可小一点。
```

---

## 模板 3：修复（自检报错时发）

<!-- template: fix -->
```text
你刚才写的部件「{{part_name}}」（id: {{part_id}}）没通过自检。

自检报告：
{{issues}}

它的装配约束：position={{position}}，bound={{bound}}，容器关系：{{inside_rule}}

你上次输出的 JSON：
{{previous_json}}

请只修改导致报错的地方，输出完整的新 JSON（不要解释）。修的时候先说明在脑子里怎么算的：
哪个尺寸超了、应该缩到多少，再输出。不要改动没报错的形状。
```

---

## 手动使用时的最小流程

1. 把模板 1 的 `{{description}}` 换成你要的东西，附上一段真实资料（维基页面正文、产品说明书……），拿到 `plan.json`。
2. 对 plan 里的每个部件，按装配顺序发模板 2，把结果存成 `parts/<id>.json`。
3. 每存一个就跑 `python3 step_by_step_3d_builder.py test 你的目录 --only <id>`，报错就发模板 3。
4. 全部通过后 `build`，得到单文件网页。
