# Design System — A股全量信息检索知识库

## Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#0f1117` | Page background |
| `--surface` | `#1a1d2e` | Cards, modals, nav |
| `--surface-hover` | `#2a2d3e` | Hover states, borders |
| `--text` | `#e8eaf0` | Primary text |
| `--text-secondary` | `#8b8fa3` | Labels, metadata |
| `--text-muted` | `#5a5d6e` | Placeholders, timestamps |
| `--primary` | `#4c6ef5` | Links, buttons, active states |
| `--primary-hover` | `#3b5de7` | Button hover |
| `--positive` | `#2ecc71` | Positive sentiment, success, healthy |
| `--negative` | `#e74c3c` | Negative sentiment, errors |
| `--neutral` | `#95a5a6` | Neutral sentiment |
| `--warning` | `#f39c12` | Warnings, degraded |
| `--type-announcement` | `#2a4a7f` / `#6ea8fe` | Announcement badge |
| `--type-financial` | `#2a6f4a` / `#6ee7a0` | Financial badge |
| `--type-capital` | `#6f2a6f` / `#d66fd6` | Capital flow badge |
| `--type-social` | `#6f5a2a` / `#e7c66e` | Social/media badge |

## Typography

- **Heading**: System sans-serif, `font-weight: 600-700`, sizes 22-28px
- **Body**: System sans-serif, `font-weight: 400`, 14-15px, line-height 1.6
- **Mono**: `"SF Mono", "Fira Code", "Consolas", monospace` for codes, dates, data values

## Spacing Scale

- xs: 4px, sm: 8px, md: 12px, lg: 16px, xl: 24px, 2xl: 32px, 3xl: 48px

## Component Patterns

### Buttons
- Primary: `--primary` bg, white text, 6px radius, hover darkens
- Secondary: transparent bg, `--surface-hover` border, hover fills
- Export: `--positive` bg for data export actions
- Trigger: `--primary` bg for system actions

### Cards
- Background: `--surface`, border `--surface-hover`, 8px radius
- Hover: border changes to `--primary`

### Tables
- Header: `--surface` bg, `--text-secondary` text, bottom border
- Rows: transparent, hover highlights to `--surface`
- Data cells: mono font, 13px

### Badges
- Type badges: colored bg + lighter text, 3px radius, 11px uppercase
- Sentiment badges: dark bg + colored text, 3px radius

### Timeline
- Vertical line: `--surface-hover` bg, 2px width
- Dots: 12px, `--primary` border, `--bg` fill
- Items: cards with left padding for line clearance

### Status Indicators
- Dot: 10px circle, colored bg + glow box-shadow
- Green/yellow/red for healthy/degraded/unhealthy

### Modal
- Overlay: rgba(0,0,0,0.6), centered
- Content: `--surface` bg, 12px radius, max 720px, scrollable

## UX Rules

1. **Search-first hierarchy**: Homepage maximizes search box visibility; all data pages accessible within 2 clicks
2. **Color-coded sentiment**: Green = positive, red = negative, gray = neutral — consistent across timeline, tables, and charts
3. **Progressive disclosure**: Timeline shows summary; click to expand details in modal — never overwhelm with text
4. **Empty states**: All data views show "暂无数据" placeholder when no results
5. **Immediate feedback**: Filter clicks update UI instantly; API calls show loading state
6. **Responsive**: Single-column layout below 768px; nav tabs wrap; search box stacks vertically

## Screen Coverage

| Screen | Journey | Key Elements |
|--------|---------|-------------|
| S1 搜索仪表盘 | J1-1, J2-1 | Search box, quick stocks, system status summary |
| S2 个股事件链 | J1-2~J1-5 | Stock header, time range, type filters, timeline |
| S3 搜索结果 | J2-2~J2-5 | Query bar, result list with highlights, filters |
| S4 因子数据 | J3-1~J3-4 | Stock selector, factor table/chart toggle, export |
| S5 系统状态 | J4-1~J4-4 | Health cards, ETL logs, trigger buttons |
| S6 事件详情弹窗 | J1-3, J2-3 | Title, meta, content, source, related events |
