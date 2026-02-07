import { useState, useMemo } from "react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { useOrchestratorStore } from "@/stores/orchestrator-store";
import { NODE_LABELS } from "@/utils/constants";
import { cn } from "@/utils/cn";
import { Database, ChevronRight, Search } from "lucide-react";

interface JsonNodeProps {
  keyName: string;
  value: unknown;
  depth: number;
  changedKeys: Set<string>;
  path: string;
  searchTerm: string;
}

function JsonNode({ keyName, value, depth, changedKeys, path, searchTerm }: JsonNodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const fullPath = path ? `${path}.${keyName}` : keyName;
  const isChanged = changedKeys.has(keyName) || changedKeys.has(fullPath);
  const indent = depth * 16;

  // Filter by search term
  const matchesSearch =
    !searchTerm ||
    keyName.toLowerCase().includes(searchTerm.toLowerCase()) ||
    String(value).toLowerCase().includes(searchTerm.toLowerCase());

  if (!matchesSearch && typeof value !== "object") return null;

  if (value === null) {
    return (
      <div
        style={{ paddingLeft: indent }}
        className={cn(
          "flex items-center gap-1 rounded px-1 py-0.5 text-[11px]",
          isChanged && "animate-change-flash border-l-2 border-amber-500/50",
        )}
      >
        <span className="text-slate-400">{keyName}:</span>
        <span className="text-slate-600 italic">null</span>
      </div>
    );
  }

  if (typeof value === "boolean") {
    return (
      <div
        style={{ paddingLeft: indent }}
        className={cn(
          "flex items-center gap-1 rounded px-1 py-0.5 text-[11px]",
          isChanged && "animate-change-flash border-l-2 border-amber-500/50",
        )}
      >
        <span className="text-slate-400">{keyName}:</span>
        <span className="text-amber-300">{String(value)}</span>
      </div>
    );
  }

  if (typeof value === "number") {
    return (
      <div
        style={{ paddingLeft: indent }}
        className={cn(
          "flex items-center gap-1 rounded px-1 py-0.5 text-[11px]",
          isChanged && "animate-change-flash border-l-2 border-amber-500/50",
        )}
      >
        <span className="text-slate-400">{keyName}:</span>
        <span className="text-blue-300">{value}</span>
      </div>
    );
  }

  if (typeof value === "string") {
    const display = value.length > 60 ? value.slice(0, 60) + "..." : value;
    return (
      <div
        style={{ paddingLeft: indent }}
        className={cn(
          "flex items-center gap-1 rounded px-1 py-0.5 text-[11px]",
          isChanged && "animate-change-flash border-l-2 border-amber-500/50",
        )}
      >
        <span className="text-slate-400">{keyName}:</span>
        <span className="text-emerald-300 truncate">&quot;{display}&quot;</span>
      </div>
    );
  }

  if (Array.isArray(value)) {
    return (
      <div
        style={{ paddingLeft: indent }}
        className={cn(
          "rounded px-1",
          isChanged && "animate-change-flash border-l-2 border-amber-500/50",
        )}
      >
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 py-0.5 text-[11px]"
        >
          <ChevronRight
            className={cn(
              "h-3 w-3 text-slate-600 transition-transform",
              expanded && "rotate-90",
            )}
          />
          <span className="text-slate-400">{keyName}:</span>
          <span className="text-slate-600">[{value.length} items]</span>
        </button>
        {expanded && (
          <div>
            {value.map((item, i) => (
              <JsonNode
                key={i}
                keyName={String(i)}
                value={item}
                depth={depth + 1}
                changedKeys={changedKeys}
                path={fullPath}
                searchTerm={searchTerm}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  if (typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    return (
      <div
        style={{ paddingLeft: indent }}
        className={cn(
          "rounded px-1",
          isChanged && "animate-change-flash border-l-2 border-amber-500/50",
        )}
      >
        <button
          onClick={() => setExpanded(!expanded)}
          className="flex items-center gap-1 py-0.5 text-[11px]"
        >
          <ChevronRight
            className={cn(
              "h-3 w-3 text-slate-600 transition-transform",
              expanded && "rotate-90",
            )}
          />
          <span className="text-slate-400">{keyName}:</span>
          <span className="text-slate-600">{`{${keys.length} keys}`}</span>
        </button>
        {expanded && (
          <div>
            {keys.map((k) => (
              <JsonNode
                key={k}
                keyName={k}
                value={(value as Record<string, unknown>)[k]}
                depth={depth + 1}
                changedKeys={changedKeys}
                path={fullPath}
                searchTerm={searchTerm}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      style={{ paddingLeft: indent }}
      className="flex items-center gap-1 px-1 py-0.5 text-[11px]"
    >
      <span className="text-slate-400">{keyName}:</span>
      <span className="text-slate-300">{String(value)}</span>
    </div>
  );
}

export function StateInspector() {
  const stateSnapshots = useOrchestratorStore((s) => s.stateSnapshots);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const activeSnapshot = useMemo(() => {
    if (stateSnapshots.length === 0) return null;
    const idx = selectedIndex ?? stateSnapshots.length - 1;
    return stateSnapshots[idx] ?? null;
  }, [stateSnapshots, selectedIndex]);

  const changedKeysSet = useMemo(
    () => new Set(activeSnapshot?.changedKeys ?? []),
    [activeSnapshot],
  );

  return (
    <GlassPanel className="flex flex-col space-y-3">
      <div className="flex items-center gap-2">
        <Database className="h-4 w-4 text-slate-400" />
        <h4 className="text-sm font-semibold text-slate-200">State Inspector</h4>
      </div>

      {stateSnapshots.length === 0 ? (
        <p className="py-8 text-center text-xs text-slate-600">
          No state snapshots yet
        </p>
      ) : (
        <>
          {/* Snapshot selector */}
          <div className="flex gap-1 overflow-x-auto pb-1">
            {stateSnapshots.map((snap, i) => (
              <button
                key={`${snap.node}-${snap.timestamp}`}
                onClick={() => setSelectedIndex(i)}
                className={cn(
                  "shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium transition-colors",
                  (selectedIndex ?? stateSnapshots.length - 1) === i
                    ? "bg-brand-500/20 text-brand-300"
                    : "text-slate-500 hover:bg-white/5 hover:text-slate-300",
                )}
              >
                {NODE_LABELS[snap.node]}
              </button>
            ))}
          </div>

          {/* Search */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-600" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter keys..."
              className="w-full rounded-lg border border-white/5 bg-white/[0.03] py-1.5 pl-7 pr-3 text-[11px] text-slate-300 placeholder:text-slate-600 focus:border-brand-500/30 focus:outline-none"
            />
          </div>

          {/* Changed keys badges */}
          {activeSnapshot && activeSnapshot.changedKeys.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {activeSnapshot.changedKeys.map((key) => (
                <span
                  key={key}
                  className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[9px] text-amber-400 border border-amber-500/20"
                >
                  {key}
                </span>
              ))}
            </div>
          )}

          {/* JSON Tree */}
          <div className="max-h-[300px] overflow-y-auto pr-1">
            {activeSnapshot &&
              Object.entries(activeSnapshot.state).map(([key, val]) => (
                <JsonNode
                  key={key}
                  keyName={key}
                  value={val}
                  depth={0}
                  changedKeys={changedKeysSet}
                  path=""
                  searchTerm={searchTerm}
                />
              ))}
          </div>
        </>
      )}
    </GlassPanel>
  );
}
