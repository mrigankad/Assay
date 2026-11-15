/**
 * Assay icon set: 24px grid, 1.75 stroke, round caps. Source of truth: brand/icons/*.svg.
 * Usage: <Icon name="verify" className="w-4 h-4 text-assay" />
 */
const PATHS: Record<string, string> = {
  'airgap': "<path d=\"M3 3l18 18\"/><path d=\"M8 18h9a4 4 0 0 0 1.6-7.7A6 6 0 0 0 9.5 7.2M5.5 9.5A4.5 4.5 0 0 0 8 18\"/>",
  'ask': "<path d=\"M4 5h16v11H9l-5 4z\"/><path d=\"M9 10.5h6\"/>",
  'audit': "<path d=\"M4 12a8 8 0 1 0 2.4-5.7L4 8.5\"/><path d=\"M4 4v4.5h4.5M12 8v4l3 2\"/>",
  'bbox': "<path d=\"M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4\"/><path d=\"M8 10h8M8 14h5\"/>",
  'check': "<path d=\"M5 12.5l4.5 4.5L19 7.5\"/>",
  'chevron': "<path d=\"M6 9l6 6 6-6\"/>",
  'collection': "<path d=\"M6 4h12M4 7.5h16\"/><rect x=\"4\" y=\"11\" width=\"16\" height=\"9\" rx=\"1.5\"/>",
  'conflict': "<path d=\"M7 3v6a5 5 0 0 0 5 5M17 3v6a5 5 0 0 1-5 5v7\"/>",
  'connect': "<path d=\"M9 3v5M15 3v5M7 8h10v3a5 5 0 0 1-10 0zM12 16v5\"/>",
  'cost': "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M14.5 9H11a2 2 0 0 0 0 4h2a2 2 0 0 1 0 4H9.5M12 6.5V9M12 17v2.5\"/>",
  'document': "<path d=\"M6 3h8l4 4v14H6z\"/><path d=\"M14 3v4h4M9 13h6M9 17h4\"/>",
  'dropped': "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M9 9l6 6M15 9l-6 6\"/>",
  'evals': "<circle cx=\"12\" cy=\"12\" r=\"8.5\"/><circle cx=\"12\" cy=\"12\" r=\"4.5\"/><circle cx=\"12\" cy=\"12\" r=\"0.8\" fill=\"currentColor\"/>",
  'expert': "<circle cx=\"12\" cy=\"8\" r=\"4\"/><path d=\"M5 21c1-4 4-6 7-6s6 2 7 6\"/>",
  'export': "<path d=\"M14 3h7v7M21 3l-9 9\"/><path d=\"M19 14v6H4V5h6\"/>",
  'lock': "<rect x=\"5\" y=\"11\" width=\"14\" height=\"10\" rx=\"2\"/><path d=\"M8 11V7a4 4 0 0 1 8 0v4\"/>",
  'logout': "<path d=\"M15 4h4v16h-4\"/><path d=\"M10 8l-4 4 4 4M6 12h10\"/>",
  'menu': "<path d=\"M4 7h16M4 12h16M4 17h16\"/>",
  'models': "<rect x=\"7\" y=\"7\" width=\"10\" height=\"10\" rx=\"1.5\"/><path d=\"M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4\"/>",
  'planner': "<circle cx=\"6\" cy=\"5\" r=\"2\"/><circle cx=\"18\" cy=\"19\" r=\"2\"/><path d=\"M8 5h7a3.5 3.5 0 0 1 0 7H9a3.5 3.5 0 0 0 0 7h7\"/>",
  'plus': "<path d=\"M12 5v14M5 12h14\"/>",
  'refresh': "<path d=\"M20 11a8 8 0 1 0-2.3 5.7\"/><path d=\"M20 4v7h-7\"/>",
  'reports': "<path d=\"M5 20V11M10 20V5M15 20v-7M20 20v-10\"/>",
  'search': "<circle cx=\"11\" cy=\"11\" r=\"6.5\"/><path d=\"M20 20l-4.3-4.3\"/>",
  'settings': "<path d=\"M4 7h10M18 7h2M4 17h4M12 17h8\"/><circle cx=\"16\" cy=\"7\" r=\"2\"/><circle cx=\"10\" cy=\"17\" r=\"2\"/>",
  'snapshot': "<rect x=\"3\" y=\"7\" width=\"18\" height=\"13\" rx=\"2\"/><circle cx=\"12\" cy=\"13.5\" r=\"3.5\"/><path d=\"M9 7l1.5-3h3L15 7\"/>",
  'table': "<rect x=\"4\" y=\"5\" width=\"16\" height=\"14\" rx=\"1.5\"/><path d=\"M4 10h16M10 10v9\"/>",
  'upload': "<path d=\"M12 16V4M7 9l5-5 5 5M4 20h16\"/>",
  'verify': "<path d=\"M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6z\"/><path d=\"M9 12l2 2 4-4\"/>",
  'web': "<circle cx=\"12\" cy=\"12\" r=\"9\"/><path d=\"M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18\"/>",
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, className = 'w-[18px] h-[18px]', strokeWidth = 1.75, title }: {
    name: string; className?: string; strokeWidth?: number; title?: string;
}) {
    return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth}
            strokeLinecap="round" strokeLinejoin="round" className={className}
            role={title ? 'img' : undefined} aria-hidden={title ? undefined : true} aria-label={title}
            dangerouslySetInnerHTML={{ __html: (title ? `<title>${title}</title>` : '') + (PATHS[name] ?? '') }} />
    );
}
