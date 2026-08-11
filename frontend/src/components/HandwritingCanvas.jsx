import { forwardRef, useImperativeHandle, useRef, useEffect, useState } from 'react';
import { Pencil, Eraser, Trash2 } from 'lucide-react';

/**
 * Reusable handwriting/whiteboard canvas. Draw with mouse, touch, or stylus.
 * Exposes an imperative API via ref:
 *   getBlob()  → Promise<Blob|null>   PNG of the drawing
 *   clear()                            wipe to white
 *   isBlank()  → boolean               true if nothing was drawn
 */
const HandwritingCanvas = forwardRef(function HandwritingCanvas(
  { width = 760, height = 300, className = '' },
  ref,
) {
  const canvasRef = useRef(null);
  const drawing = useRef(false);
  const lastPt = useRef(null);
  const dirty = useRef(false);
  const [tool, setTool] = useState('pen');
  const toolRef = useRef('pen');
  useEffect(() => { toolRef.current = tool; }, [tool]);

  const paintWhite = () => {
    const c = canvasRef.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(0, 0, c.width, c.height);
    dirty.current = false;
  };

  useEffect(() => { paintWhite(); }, []);

  useImperativeHandle(ref, () => ({
    getBlob: () => new Promise((resolve) => {
      const c = canvasRef.current;
      if (!c) return resolve(null);
      c.toBlob(resolve, 'image/png');
    }),
    clear: paintWhite,
    isBlank: () => !dirty.current,
  }));

  const getPos = (e) => {
    const c = canvasRef.current;
    const rect = c.getBoundingClientRect();
    return {
      x: (e.clientX - rect.left) * (c.width / rect.width),
      y: (e.clientY - rect.top) * (c.height / rect.height),
    };
  };
  const start = (e) => { e.preventDefault(); drawing.current = true; lastPt.current = getPos(e); };
  const move = (e) => {
    if (!drawing.current) return;
    e.preventDefault();
    const ctx = canvasRef.current.getContext('2d');
    const p = getPos(e);
    ctx.strokeStyle = toolRef.current === 'eraser' ? '#ffffff' : '#111827';
    ctx.lineWidth = toolRef.current === 'eraser' ? 26 : 3.5;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(lastPt.current.x, lastPt.current.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    lastPt.current = p;
    dirty.current = true;
  };
  const end = () => { drawing.current = false; lastPt.current = null; };

  return (
    <div className={className}>
      <div className="flex items-center gap-2 mb-2">
        <button type="button" onClick={() => setTool('pen')}
          className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg ${tool === 'pen' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
          <Pencil size={14} /> Pen
        </button>
        <button type="button" onClick={() => setTool('eraser')}
          className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg ${tool === 'eraser' ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-600'}`}>
          <Eraser size={14} /> Eraser
        </button>
        <button type="button" onClick={paintWhite}
          className="ml-auto flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 hover:bg-red-50 hover:text-red-600">
          <Trash2 size={14} /> Clear
        </button>
      </div>
      <div className="rounded-2xl overflow-hidden border-2 border-slate-200 shadow-soft bg-white">
        <canvas
          ref={canvasRef}
          width={width}
          height={height}
          onPointerDown={start}
          onPointerMove={move}
          onPointerUp={end}
          onPointerLeave={end}
          className="w-full block cursor-crosshair"
          style={{ touchAction: 'none', aspectRatio: `${width} / ${height}` }}
        />
      </div>
    </div>
  );
});

export default HandwritingCanvas;
