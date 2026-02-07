import { useId } from "react";

interface AnimatedEdgeProps {
  fromX: number;
  fromY: number;
  toX: number;
  toY: number;
  active: boolean;
  isConditional: boolean;
}

function buildPath(fx: number, fy: number, tx: number, ty: number): string {
  const dx = tx - fx;
  const dy = ty - fy;
  // Perpendicular offset for curve control point
  const len = Math.sqrt(dx * dx + dy * dy) || 1;
  const nx = -dy / len;
  const ny = dx / len;
  const offset = Math.min(len * 0.2, 30);
  const cx = (fx + tx) / 2 + nx * offset;
  const cy = (fy + ty) / 2 + ny * offset;
  return `M ${fx} ${fy} Q ${cx} ${cy} ${tx} ${ty}`;
}

export function AnimatedEdge({
  fromX,
  fromY,
  toX,
  toY,
  active,
  isConditional,
}: AnimatedEdgeProps) {
  const uid = useId();
  const pathId = `edge-path-${uid}`;
  const d = buildPath(fromX, fromY, toX, toY);

  const baseStroke = isConditional ? "#f59e0b30" : "#334155";
  const activeStroke = isConditional ? "#f59e0b60" : "#f59e0b50";

  return (
    <g>
      {/* Base path */}
      <path
        d={d}
        fill="none"
        stroke={active ? activeStroke : baseStroke}
        strokeWidth={active ? 2 : 1.5}
        strokeDasharray={isConditional ? "6 4" : undefined}
        className={active ? "animate-edge-pulse" : undefined}
      />

      {/* Animated particles when active */}
      {active && (
        <>
          <path id={pathId} d={d} fill="none" stroke="none" />
          {[0, 0.33, 0.66].map((offset) => (
            <circle
              key={offset}
              r={2.5}
              fill="#f59e0b"
              opacity={0.7}
            >
              <animateMotion
                dur="1.8s"
                repeatCount="indefinite"
                begin={`${offset * 1.8}s`}
              >
                <mpath href={`#${pathId}`} />
              </animateMotion>
            </circle>
          ))}
        </>
      )}
    </g>
  );
}
