import { useEffect, useState } from 'react';
import api from '@/services/api';

/** The real PDF page with the cited passage boxed. Renders nothing for non-PDFs or on failure. */
export function PageHighlight({ documentId, page, text }: { documentId: string; page: number; text: string }) {
    const [src, setSrc] = useState<string | null>(null);
    const [rects, setRects] = useState<number[][]>([]);
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        let url: string | null = null;
        let live = true;
        setSrc(null); setRects([]); setFailed(false);
        Promise.all([
            api.get(`/documents/${documentId}/pages/${page}.png`, { responseType: 'blob' }),
            api.post(`/documents/${documentId}/pages/${page}/locate`, { text }),
        ]).then(([img, loc]) => {
            if (!live) return;
            url = URL.createObjectURL(img.data);
            setSrc(url);
            setRects(loc.data.rects ?? []);
        }).catch(() => live && setFailed(true));
        return () => { live = false; if (url) URL.revokeObjectURL(url); };
    }, [documentId, page, text]);

    if (failed) return null;
    if (!src) return <div className="aspect-[612/792] w-full animate-pulse rounded-md bg-paper" />;
    return (
        <div className="w-full shrink-0 overflow-hidden rounded-md bg-paper shadow-[0_1px_0_#E4E8E0]">
          {/* Boxes are percentages of this wrapper, which is exactly the image's size */}
          <div className="relative">
            <img src={src} alt={`Page ${page}`} className="block h-auto w-full max-w-none" />
            {rects.map(([x0, y0, x1, y1], i) => (
                <span key={i} className="absolute rounded-[2px] border-2 border-assay bg-lime/40 mix-blend-multiply"
                    style={{ left: `${x0 * 100}%`, top: `${y0 * 100}%`, width: `${(x1 - x0) * 100}%`, height: `${(y1 - y0) * 100}%` }} />
            ))}
            {!rects.length && (
                <span className="absolute bottom-2 left-2 rounded-full bg-ink/80 px-2.5 py-1 text-[11px] text-white">Passage not located exactly on this page</span>
            )}
          </div>
        </div>
    );
}
