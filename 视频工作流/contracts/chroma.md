# chroma ·绿 抠像/贴合  史:notes/chroma.md

接口: chroma_key(bgr), flood_key(bgr,tol=10)*多色背景首选, clean_mask,
      contact_shadow, overlay, load_character, trim_alpha
参数: shrink=2(1px contract)｜feather=0.5｜load_character 默认 method="flood"
注意: flood_key 的 alpha 是 0-1 float，阈值用 0.5 不是 128

**self_check()（铁律26）**
`python3 chroma.py` 默认自检，不读真实资产（用合成图，避免依赖资产目录）。检查项：
  1. chroma_key 能识别纯色背景并产出 alpha（前景/背景分离）
  2. flood_key 的 alpha 是 0-1 float，阈值必须 0.5 不是 128（契约已注明）
  3. trim_alpha 裁到内容包围盒且 pad 生效
  4. overlay 不越界、alpha 混合后背景不被整体污染
  5. 【铁律15】形状合理性：只拦【极端】异常，并输出主色供复核
     ⚠ 实测局限：历史 bug 资产宽高比 0.264，落在合理区间内 —— 纯几何拦不住。
       真正区分它的是主色(BGR[37,52,118] 蓝色)与水平分离前景块，
       需与声明物性比对才成立。故形态判断归 AI（铁律18），代码不越界。
