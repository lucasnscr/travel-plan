import { INTEREST_PRESETS } from "@/utils/constants";
import { cn } from "@/utils/cn";

interface InterestTagsProps {
  selected: string[];
  onToggle: (value: string) => void;
}

export function InterestTags({ selected, onToggle }: InterestTagsProps) {
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-slate-400">Interests</label>
      <div className="flex flex-wrap gap-2">
        {INTEREST_PRESETS.map((tag) => {
          const active = selected.includes(tag.value);
          return (
            <button
              key={tag.value}
              type="button"
              onClick={() => onToggle(tag.value)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs font-medium transition-all",
                active
                  ? "border-brand-500/40 bg-brand-500/20 text-brand-300"
                  : "border-white/10 bg-white/5 text-slate-400 hover:border-white/20 hover:text-slate-300",
              )}
            >
              {tag.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
