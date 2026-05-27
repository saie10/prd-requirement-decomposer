# Usage Examples

以下命令默认在仓库根目录执行。

## 单页抽取

```bash
scripts/extract_prd_pages.sh \
  --scope-page '15899·指标卡支持选择时间范围、适配查询粒度、自定义数值格式' \
  'https://axhub.im/ax9/88a869475d1591b8/#id=4o2e14&p=15899%C2%B7%E6%8C%87%E6%A0%87%E5%8D%A1%E6%94%AF%E6%8C%81%E9%80%89%E6%8B%A9%E6%97%B6%E9%97%B4%E8%8C%83%E5%9B%B4%E3%80%81%E9%80%82%E9%85%8D%E6%9F%A5%E8%AF%A2%E7%B2%92%E5%BA%A6%E3%80%81%E8%87%AA%E5%AE%9A%E4%B9%89%E6%95%B0%E5%80%BC%E6%A0%BC%E5%BC%8F&g=1'
```

## 目录抽取

```bash
scripts/extract_prd_pages.sh \
  --scope-dir '第一批交付（4.24 上线V6.2）' \
  'https://modao.cc/axbox/share/A8gSs7CCtdfpdeZHeNf4iI?screen=wstu2q&s=0'
```

## 显式保留截图

```bash
scripts/extract_prd_pages.sh \
  --with-screenshot \
  --scope-page '15686·自助取数-新增明细查询' \
  'https://modao.cc/axbox/share/A8gSs7CCtdfpdeZHeNf4iI?screen=wstu2q&s=0'
```

## 指定输出模式

```bash
scripts/extract_prd_pages.sh \
  --output-mode rich \
  --scope-page '15900·指标看板同环比功能适配' \
  'https://axhub.im/ax9/88a869475d1591b8/#id=4o2e14&p=15900%C2%B7%E6%8C%87%E6%A0%87%E7%9C%8B%E6%9D%BF%E5%90%8C%E7%8E%AF%E6%AF%94%E5%8A%9F%E8%83%BD%E9%80%82%E9%85%8D&g=1'
```

## 推荐读取顺序

抽取完成后，推荐先看：

1. `extraction-summary.json`
2. `understanding-input.json`

如果还需要回溯：

3. `pages.json`
4. `page-*/page.json`
