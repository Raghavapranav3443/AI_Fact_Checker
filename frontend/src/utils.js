export const VERDICT_META = {
  'TRUE':           { color: 'var(--true)',          bg: 'var(--true-bg)',          border: 'var(--true-border)',          label: 'True',          symbol: '✓' },
  'FALSE':          { color: 'var(--false)',          bg: 'var(--false-bg)',         border: 'var(--false-border)',         label: 'False',         symbol: '✗' },
  'PARTIALLY TRUE': { color: 'var(--partial)',        bg: 'var(--partial-bg)',       border: 'var(--partial-border)',       label: 'Partial',       symbol: '◑' },
  'UNVERIFIABLE':   { color: 'var(--unverifiable)',   bg: 'var(--unverifiable-bg)',  border: 'var(--unverifiable-border)',  label: 'Unverifiable',  symbol: '?' },
  'CONTESTED':      { color: 'var(--contested)',      bg: 'var(--contested-bg)',     border: 'var(--contested-border)',     label: 'Contested',     symbol: '⚡' },
}

export function getVerdict(v) {
  return VERDICT_META[v] || VERDICT_META['UNVERIFIABLE']
}

export function confidenceColor(score) {
  if (score >= 80) return 'var(--true)'
  if (score >= 50) return 'var(--partial)'
  return 'var(--false)'
}

export function trustLabel(score) {
  if (score >= 80) return 'High Trust'
  if (score >= 60) return 'Moderate Trust'
  if (score >= 40) return 'Low Trust'
  return 'Very Low Trust'
}

export function claimTypeColor(type) {
  const map = {
    'Temporal':        '#60a5fa',
    'Statistical':     '#34d399',
    'Entity Status':   '#a78bfa',
    'Historical Fact': '#fbbf24',
  }
  return map[type] || '#8899bb'
}
