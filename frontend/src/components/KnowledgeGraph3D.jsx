import { useRef, useCallback, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';

/**
 * Interactive 2D force-directed knowledge graph.
 * Nodes = topics (sized & coloured by mastery).
 * Edges = prerequisite/relation links from the API.
 */
export default function KnowledgeGraphViz({ data, width = 500, height = 360 }) {
  const fgRef = useRef();

  const graphData = useMemo(() => {
    if (!data?.nodes?.length) return { nodes: [], links: [] };

    const nodes = data.nodes.map((n) => ({
      id: n.topic,
      mastery: n.mastery,
      isFocus: data.suggested_focus?.toLowerCase().includes(n.topic.toLowerCase()),
      isWeak: data.weak_links?.some(w => w.toLowerCase() === n.topic.toLowerCase()),
    }));

    const nodeIds = new Set(nodes.map(n => n.id));

    const links = (data.edges || [])
      .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map(e => ({
        source: e.source,
        target: e.target,
        strength: e.strength,
        reason: e.reason,
      }));

    return { nodes, links };
  }, [data]);

  const nodeColor = useCallback((node) => {
    if (node.isFocus) return '#d9b86e';  // gold for focus
    if (node.isWeak) return '#f87171';   // coral for weak
    if (node.mastery > 0.7) return '#34d399';  // emerald
    if (node.mastery > 0.4) return '#2dd4bf';  // teal
    return '#7c8a99';  // muted
  }, []);

  const nodeSize = useCallback((node) => {
    return 6 + node.mastery * 14;
  }, []);

  const nodeLabel = useCallback((node) => {
    return `${node.id} — ${(node.mastery * 100).toFixed(0)}% mastery`;
  }, []);

  const paintNode = useCallback((node, ctx, globalScale) => {
    const size = nodeSize(node);
    const fontSize = Math.max(10 / globalScale, 2);
    const color = nodeColor(node);

    // Circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();

    // Glow for focus nodes
    if (node.isFocus) {
      ctx.strokeStyle = '#d9b86e';
      ctx.lineWidth = 2 / globalScale;
      ctx.stroke();
    }

    // Label
    ctx.font = `${fontSize}px sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    ctx.fillStyle = '#8b96a9';
    ctx.fillText(node.id, node.x, node.y + size + 2);
  }, [nodeColor, nodeSize]);

  const linkColor = useCallback((link) => {
    if (link.strength === 'strong') return 'rgba(45, 212, 191, 0.55)';
    if (link.strength === 'weak') return 'rgba(248, 113, 113, 0.4)';
    return 'rgba(124, 138, 153, 0.35)';
  }, []);

  if (!graphData.nodes.length) {
    return (
      <div className="flex items-center justify-center h-64 text-ink-faint text-sm">
        Study more topics to see your knowledge graph
      </div>
    );
  }

  return (
    <ForceGraph2D
      ref={fgRef}
      graphData={graphData}
      width={width}
      height={height}
      nodeCanvasObject={paintNode}
      nodePointerAreaPaint={(node, color, ctx) => {
        ctx.beginPath();
        ctx.arc(node.x, node.y, nodeSize(node) + 4, 0, 2 * Math.PI);
        ctx.fillStyle = color;
        ctx.fill();
      }}
      linkColor={linkColor}
      linkWidth={(link) => link.strength === 'strong' ? 2 : 1}
      linkDirectionalParticles={1}
      linkDirectionalParticleWidth={2}
      cooldownTicks={60}
      enableZoomInteraction={true}
      enablePanInteraction={true}
      backgroundColor="transparent"
    />
  );
}
