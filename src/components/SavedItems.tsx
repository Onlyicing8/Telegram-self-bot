import type { SavedItem } from '../lib/api';

interface Props {
  items: SavedItem[];
  total: number;
}

const TYPE_COLORS: Record<string, string> = {
  Photo: 'text-sky-400 bg-sky-400/10',
  Video: 'text-violet-400 bg-violet-400/10',
  Animation: 'text-amber-400 bg-amber-400/10',
  Audio: 'text-emerald-400 bg-emerald-400/10',
  Voice: 'text-teal-400 bg-teal-400/10',
  Sticker: 'text-pink-400 bg-pink-400/10',
  Document: 'text-slate-400 bg-slate-400/10',
  Unknown: 'text-slate-500 bg-slate-500/10',
};

function fmt(bytes: number | null): string {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function SavedItems({ items, total }: Props) {
  if (!items.length) {
    return (
      <div className="flex flex-col items-center justify-center h-48 text-on-surface-variant">
        <p className="text-sm">No saved items yet.</p>
        <p className="text-xs mt-1 opacity-60">Use <code className="font-mono">.save f</code> or <code className="font-mono">.save d</code> in Telegram.</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-on-surface-variant uppercase tracking-widest">
          Saved Items
        </h2>
        <span className="text-xs text-on-surface-variant">{total} total</span>
      </div>

      <div className="space-y-2">
        {items.map(item => {
          const typeColor = TYPE_COLORS[item.media_type || 'Unknown'] || TYPE_COLORS.Unknown;
          return (
            <div
              key={item.id}
              className="group bg-surface-container rounded-2xl px-5 py-4 border border-outline-variant hover:border-primary/40 transition-colors"
            >
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`shrink-0 text-xs font-mono px-2 py-0.5 rounded-full ${typeColor}`}>
                    {item.media_type || 'Unknown'}
                  </span>
                  <span className="font-mono text-sm font-medium text-primary truncate">
                    {item.save_code}
                  </span>
                  {item.file_name && (
                    <span className="text-xs text-on-surface-variant truncate hidden sm:inline">
                      {item.file_name}
                    </span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    item.save_type === 'deep'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-amber-500/10 text-amber-400'
                  }`}>
                    {item.save_type}
                  </span>
                </div>
                <span className="shrink-0 text-xs text-on-surface-variant">
                  {relativeTime(item.created_at)}
                </span>
              </div>

              <div className="mt-2.5 grid grid-cols-2 sm:grid-cols-4 gap-x-6 gap-y-1 text-xs text-on-surface-variant">
                <div><span className="opacity-50">Sender</span> <span className="text-on-surface">{item.sender_name || '—'}</span></div>
                <div><span className="opacity-50">Chat</span> <span className="font-mono text-on-surface">{item.origin_chat_id ?? '—'}</span></div>
                <div><span className="opacity-50">MIME</span> <span className="text-on-surface">{item.mime_type || '—'}</span></div>
                <div><span className="opacity-50">Size</span> <span className="text-on-surface">{fmt(item.file_size)}</span></div>
              </div>

              {item.file_name && (
                <div className="mt-1.5 text-xs text-on-surface-variant">
                  <span className="opacity-50">File</span> <span className="text-on-surface font-mono">{item.file_name}</span>
                </div>
              )}

              {item.tags && item.tags.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-1.5">
                  {item.tags.map(tag => (
                    <span key={tag} className="text-xs text-on-surface-variant bg-surface-variant px-2 py-0.5 rounded-full font-mono">
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
