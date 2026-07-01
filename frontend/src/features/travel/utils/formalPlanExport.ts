import type { StructuredTravelPlan } from '@/features/travel/types/itinerary';
import { sanitizeFilename } from '@/features/travel/utils/exportPlan';

export interface PlanNavLink {
  name: string;
  address?: string;
  category: string;
  url: string;
}

function escapeIcsText(value: string): string {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/\n/g, '\\n')
    .replace(/,/g, '\\,')
    .replace(/;/g, '\\;');
}

function formatIcsDate(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}` +
    `T${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`
  );
}

function parseTravelStartDate(travelDates: string | null | undefined): Date | null {
  if (!travelDates) return null;
  const match = travelDates.match(/(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})/);
  if (!match) return null;
  const [, year, month, day] = match;
  return new Date(Number(year), Number(month) - 1, Number(day), 9, 0, 0);
}

function parseActivityHour(time: string | null | undefined): number {
  if (!time) return 9;
  const match = time.match(/(\d{1,2})[:：](\d{2})/);
  if (match) return Math.min(23, Number(match[1]));
  if (time.includes('下午') || time.includes('傍晚')) return 14;
  if (time.includes('晚上') || time.includes('夜间')) return 19;
  if (time.includes('中午')) return 12;
  return 9;
}

export function buildAmapSearchUrl(
  name: string,
  options?: { address?: string | null; city?: string | null },
): string {
  const query = options?.address ? `${name} ${options.address}`.trim() : name.trim();
  const params = new URLSearchParams({ query });
  if (options?.city) params.set('city', options.city);
  return `https://uri.amap.com/search?${params.toString()}`;
}

export function collectPlanNavLinks(plan: StructuredTravelPlan): PlanNavLink[] {
  const seen = new Set<string>();
  const links: PlanNavLink[] = [];

  const add = (name: string, address?: string | null, category = '地点') => {
    const key = `${name}|${address || ''}`;
    if (!name.trim() || seen.has(key)) return;
    seen.add(key);
    links.push({
      name: name.trim(),
      address: address?.trim() || undefined,
      category,
      url: buildAmapSearchUrl(name, { address, city: plan.destination }),
    });
  };

  for (const day of plan.daily_itinerary) {
    for (const activity of day.activities) {
      if (activity.location) {
        add(activity.location.name, activity.location.address, '景点/活动');
      } else if (activity.title) {
        add(activity.title, undefined, '景点/活动');
      }
    }
  }

  for (const item of plan.accommodations) {
    add(item.name, item.address, '住宿');
  }

  return links;
}

export function buildIcsCalendar(plan: StructuredTravelPlan): string {
  const now = new Date();
  const startBase = parseTravelStartDate(plan.travel_dates) ?? new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() + 7,
    9,
    0,
    0,
  );

  const events: string[] = [];

  for (const day of plan.daily_itinerary) {
    for (const [index, activity] of day.activities.entries()) {
      const start = new Date(startBase);
      start.setDate(start.getDate() + (day.day - 1));
      start.setHours(parseActivityHour(activity.time), 0, 0, 0);

      const end = new Date(start);
      end.setHours(start.getHours() + 2);

      const location = activity.location;
      const locationText = location
        ? [location.name, location.address].filter(Boolean).join(' ')
        : plan.destination;

      const descriptionParts = [
        activity.description,
        location ? buildAmapSearchUrl(location.name, { address: location.address, city: plan.destination }) : '',
        plan.summary,
      ].filter(Boolean);

      events.push([
        'BEGIN:VEVENT',
        `UID:${sanitizeFilename(plan.title)}-d${day.day}-a${index}@my-ai-studio`,
        `DTSTAMP:${formatIcsDate(now)}`,
        `DTSTART:${formatIcsDate(start)}`,
        `DTEND:${formatIcsDate(end)}`,
        `SUMMARY:${escapeIcsText(`${plan.destination} · ${activity.title}`)}`,
        `LOCATION:${escapeIcsText(locationText)}`,
        `DESCRIPTION:${escapeIcsText(descriptionParts.join('\\n'))}`,
        'END:VEVENT',
      ].join('\r\n'));
    }
  }

  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//My AI Studio//Travel Plan//CN',
    'CALSCALE:GREGORIAN',
    'METHOD:PUBLISH',
    ...events,
    'END:VCALENDAR',
  ].join('\r\n');
}

export function downloadIcsFile(content: string, filename: string): void {
  const blob = new Blob([content], { type: 'text/calendar;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function buildFormalPlanHtml(plan: StructuredTravelPlan, documentTitle: string): string {
  const navLinks = collectPlanNavLinks(plan);
  const daySections = plan.daily_itinerary.map((day) => {
    const activities = day.activities.map((activity) => {
      const location = activity.location;
      const navUrl = location
        ? buildAmapSearchUrl(location.name, { address: location.address, city: plan.destination })
        : '';
      return `
        <div class="activity">
          <div class="activity-title">${escapeHtml(activity.time ? `${activity.time} · ${activity.title}` : activity.title)}</div>
          ${activity.description ? `<p>${escapeHtml(activity.description)}</p>` : ''}
          ${location ? `<p class="muted">📍 ${escapeHtml([location.name, location.address].filter(Boolean).join(' · '))}</p>` : ''}
          ${navUrl ? `<a href="${escapeHtml(navUrl)}" target="_blank" rel="noreferrer">高德导航</a>` : ''}
        </div>
      `;
    }).join('');

    return `
      <section class="day-card">
        <h3>Day ${day.day}${day.title ? ` · ${escapeHtml(day.title)}` : ''}</h3>
        ${activities}
      </section>
    `;
  }).join('');

  const metaItems = [
    `<div class="meta-item"><span>目的地</span><strong>${escapeHtml(plan.destination)}</strong></div>`,
    plan.duration_days != null
      ? `<div class="meta-item"><span>天数</span><strong>${plan.duration_days} 天</strong></div>`
      : '',
    plan.travel_dates
      ? `<div class="meta-item"><span>日期</span><strong>${escapeHtml(plan.travel_dates)}</strong></div>`
      : '',
    plan.budget_total != null
      ? `<div class="meta-item"><span>预算</span><strong>${plan.budget_total} ${escapeHtml(plan.budget_currency || 'CNY')}</strong></div>`
      : '',
  ].filter(Boolean).join('');

  const navSection = navLinks.length
    ? `<section><h2>导航链接</h2><ul>${navLinks.map((item) =>
        `<li><a href="${escapeHtml(item.url)}">${escapeHtml(item.name)}</a>${item.address ? ` <span class="muted">${escapeHtml(item.address)}</span>` : ''}</li>`
      ).join('')}</ul></section>`
    : '';

  const budgetSection = plan.budget_breakdown.length
    ? `<section><h2>预算明细</h2><table><thead><tr><th>类别</th><th>金额</th><th>说明</th></tr></thead><tbody>${plan.budget_breakdown.map((item) =>
        `<tr><td>${escapeHtml(item.category)}</td><td>${item.amount != null ? `${item.amount} ${escapeHtml(item.currency || 'CNY')}` : '—'}</td><td>${escapeHtml(item.note || '—')}</td></tr>`
      ).join('')}</tbody></table></section>`
    : '';

  const fullHtml = `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(documentTitle)}</title>
  <style>
    * { box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
      color: #0f172a;
      line-height: 1.65;
      margin: 0;
      background: #f8fafc;
    }
    .page {
      max-width: 820px;
      margin: 0 auto;
      padding: 36px 28px 48px;
    }
    .hero {
      background: linear-gradient(135deg, #eff6ff, #ffffff);
      border: 1px solid #dbeafe;
      border-radius: 18px;
      padding: 24px 28px;
      margin-bottom: 24px;
    }
    .badge {
      display: inline-block;
      font-size: 12px;
      font-weight: 700;
      color: ${plan.data_verified ? '#047857' : '#b45309'};
      background: ${plan.data_verified ? '#d1fae5' : '#fef3c7'};
      border-radius: 999px;
      padding: 4px 10px;
      margin-bottom: 12px;
    }
    h1 { margin: 0 0 8px; font-size: 28px; }
    .summary { color: #475569; margin: 0; }
    .meta-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin: 24px 0;
    }
    .meta-item {
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 12px;
      padding: 12px 14px;
    }
    .meta-item span {
      display: block;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: #64748b;
      margin-bottom: 4px;
    }
    h2 {
      font-size: 18px;
      margin: 28px 0 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid #e2e8f0;
    }
    .day-card {
      background: white;
      border: 1px solid #e2e8f0;
      border-radius: 14px;
      padding: 16px 18px;
      margin-bottom: 14px;
      break-inside: avoid;
    }
    .day-card h3 { margin: 0 0 12px; font-size: 16px; color: #1d4ed8; }
    .activity { border-left: 3px solid #93c5fd; padding-left: 12px; margin-bottom: 14px; }
    .activity-title { font-weight: 700; margin-bottom: 4px; }
    .muted { color: #64748b; font-size: 13px; }
    a { color: #2563eb; text-decoration: none; font-size: 13px; }
    table { width: 100%; border-collapse: collapse; background: white; }
    th, td { border: 1px solid #e2e8f0; padding: 8px 10px; text-align: left; font-size: 14px; }
    th { background: #f1f5f9; }
    ul { padding-left: 18px; }
    .footer { margin-top: 28px; color: #94a3b8; font-size: 12px; }
    @media print {
      body { background: white; }
      .page { padding: 0; }
      a { color: #2563eb; }
    }
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <div class="badge">${plan.data_verified ? 'Agent 数据已验证' : 'AI 整理 · 请核实'}</div>
      <h1>${escapeHtml(plan.title)}</h1>
      <p class="summary">${escapeHtml(plan.summary)}</p>
    </div>
    <div class="meta-grid">${metaItems}</div>
    ${plan.weather_summary ? `<section><h2>天气参考</h2><p>${escapeHtml(plan.weather_summary)}</p></section>` : ''}
    <section><h2>每日行程</h2>${daySections}</section>
    ${navSection}
    ${budgetSection}
    ${plan.tips.length ? `<section><h2>注意事项</h2><ul>${plan.tips.map((tip) => `<li>${escapeHtml(tip)}</li>`).join('')}</ul></section>` : ''}
    <p class="footer">由 AI 生成，出行前请核实交通、票价与开放时间。</p>
  </div>
</body>
</html>`;

  return fullHtml;
}
