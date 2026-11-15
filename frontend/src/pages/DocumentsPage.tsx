import { useCallback, useEffect, useMemo, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import clsx from 'clsx';
import { useDocumentStore } from '@/stores/documentStore';
import { Icon } from '@/components/Icon';
import type { Document } from '@/types';

const ACCEPT = {
    'application/pdf': ['.pdf'],
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx'],
    'text/html': ['.html', '.htm'],
    'text/markdown': ['.md'],
    'text/csv': ['.csv'],
    'text/plain': ['.txt'],
};

function Status({ doc }: { doc: Document }) {
    if (doc.status === 'completed') {
        return <span className="flex items-center gap-1.5 text-[13px] font-semibold text-assay"><Icon name="check" className="h-3.5 w-3.5" strokeWidth={2.4} />Indexed</span>;
    }
    if (doc.status === 'failed') {
        return <span className="flex items-center gap-1.5 text-[13px] font-semibold text-dropped"><Icon name="dropped" className="h-3.5 w-3.5" strokeWidth={2} />Failed</span>;
    }
    return (
        <span className="flex flex-col gap-[5px] text-[13px] font-semibold">
            Reading…
            <span className="h-1 w-[140px] overflow-hidden rounded-full bg-rule"><span className="block h-1 w-1/2 animate-pulse rounded-full bg-ink" /></span>
        </span>
    );
}

const fmt = (n?: number) => (n === undefined || n === null ? '-' : n.toLocaleString());

export function DocumentsPage() {
    const { documents, isLoading, isUploading, fetchDocuments, uploadDocuments, deleteDocument } = useDocumentStore();
    const [query, setQuery] = useState('');
    const [confirming, setConfirming] = useState<string | null>(null);

    useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

    useEffect(() => {
        if (!documents.some((d) => d.status === 'processing')) return;
        const t = setInterval(fetchDocuments, 4000);
        return () => clearInterval(t);
    }, [documents, fetchDocuments]);

    const onDrop = useCallback((files: File[]) => { if (files.length) uploadDocuments(files); }, [uploadDocuments]);
    const { getRootProps, getInputProps, isDragActive, open } = useDropzone({ onDrop, accept: ACCEPT, multiple: true, noClick: true });

    const shown = useMemo(() => documents.filter((d) => d.filename.toLowerCase().includes(query.toLowerCase())), [documents, query]);
    const totals = useMemo(() => ({
        docs: documents.length,
        pages: documents.reduce((a, d) => a + (d.total_pages ?? 0), 0),
        chunks: documents.reduce((a, d) => a + (d.chunks_count ?? 0), 0),
    }), [documents]);

    return (
        <div {...getRootProps()} className="h-full overflow-y-auto bg-paper outline-none">
            <input {...getInputProps()} />
            <div className="mx-auto flex max-w-[1180px] flex-col gap-[22px] px-6 py-9 lg:px-12">
                <header className="flex flex-wrap items-end justify-between gap-4">
                    <div className="flex flex-col gap-2">
                        <span className="text-[13px] text-body">Workspace · Documents</span>
                        <h1 className="font-display text-[34px] font-bold leading-none">Documents</h1>
                    </div>
                    <div className="flex items-center gap-2">
                        <label className="flex h-9 items-center gap-2 rounded-[10px] border border-[#D5DBD0] px-3 text-sm">
                            <Icon name="search" className="h-4 w-4 text-body" />
                            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Filter"
                                className="w-36 bg-transparent outline-none placeholder:text-muted" />
                        </label>
                        <button onClick={open} disabled={isUploading}
                            className="flex h-9 items-center gap-2 rounded-[10px] bg-ink px-3.5 text-sm font-medium text-white disabled:opacity-60">
                            <Icon name="upload" className="h-4 w-4 text-lime" strokeWidth={2} />
                            {isUploading ? 'Uploading…' : 'Upload'}
                        </button>
                    </div>
                </header>

                <div className="flex flex-wrap gap-7 border-b border-rule pb-1 text-[13px] text-body">
                    <span><b className="font-display text-[22px] text-ink">{fmt(totals.docs)}</b>  documents</span>
                    <span><b className="font-display text-[22px] text-ink">{fmt(totals.pages)}</b>  pages</span>
                    <span><b className="font-display text-[22px] text-ink">{fmt(totals.chunks)}</b>  chunks</span>
                </div>

                {documents.length > 0 && (
                    <div className="flex flex-col text-sm">
                        <div className="flex items-center border-b border-ink pb-2.5 text-xs font-semibold text-body">
                            <span className="flex-1">Document</span>
                            <span className="hidden w-[90px] shrink-0 sm:block">Pages</span>
                            <span className="hidden w-[90px] shrink-0 sm:block">Chunks</span>
                            <span className="w-[170px] shrink-0">Status</span>
                            <span className="w-[120px] shrink-0" />
                        </div>
                        {shown.map((d) => (
                            <div key={d.id} className={clsx('flex items-center border-b border-[#EEF1EA] py-[13px]', d.status === 'processing' && 'bg-[#F7FCE8]')}>
                                <span className="flex min-w-0 flex-1 items-center gap-2.5 font-medium">
                                    <Icon name="document" className="h-[18px] w-[18px] shrink-0 text-body" />
                                    <span className="truncate">{d.filename}</span>
                                </span>
                                <span className="hidden w-[90px] shrink-0 text-body sm:block">{fmt(d.total_pages)}</span>
                                <span className="hidden w-[90px] shrink-0 text-body sm:block">{fmt(d.chunks_count)}</span>
                                <span className="w-[170px] shrink-0"><Status doc={d} /></span>
                                <span className="flex w-[120px] shrink-0 justify-end">
                                    {confirming === d.id ? (
                                        <span className="flex items-center gap-2 text-[13px]">
                                            <button onClick={() => { deleteDocument(d.id, d.filename); setConfirming(null); }} className="font-semibold text-dropped">Delete</button>
                                            <button onClick={() => setConfirming(null)} className="text-body">Keep</button>
                                        </span>
                                    ) : (
                                        <button onClick={() => setConfirming(d.id)} className="text-[13px] text-body hover:text-dropped">Remove</button>
                                    )}
                                </span>
                            </div>
                        ))}
                        {!shown.length && <p className="py-6 text-sm text-body">No documents match “{query}”.</p>}
                    </div>
                )}

                <button onClick={open}
                    className={clsx('flex items-center gap-7 rounded-[18px] border-[1.5px] border-dashed px-7 py-5 text-left transition',
                        isDragActive ? 'border-ink bg-lime-wash' : 'border-[#C9D0C4] bg-bench')}>
                    <img src="/brand/art/upload.webp" alt="" className="hidden h-[150px] w-[200px] shrink-0 rounded-xl object-cover sm:block" />
                    <span className="flex flex-col gap-1.5">
                        <span className="font-display text-[22px] font-bold">
                            {isDragActive ? 'Drop to add them' : documents.length ? 'Drop files to add more' : isLoading ? 'Loading…' : 'Add your first documents'}
                        </span>
                        <span className="text-sm leading-[21px] text-body">
                            PDF, Word, Excel, PowerPoint, HTML, Markdown, CSV and text. Tables are kept whole and every chunk remembers its page.
                        </span>
                    </span>
                </button>
            </div>
        </div>
    );
}
