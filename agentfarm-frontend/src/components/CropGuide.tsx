import { CropInfo } from '../lib/api';

interface CropGuideProps {
  crops: CropInfo[];
}

export default function CropGuide({ crops }: CropGuideProps) {
  return (
    <div className="space-y-2">
      {crops.map(crop => (
        <div
          key={crop.key}
          className="flex items-center gap-3 py-1.5 px-2 rounded-lg hover:bg-slate-800/40 transition-colors"
        >
          <span className="text-xl">{crop.emoji}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-1">
              <p className="text-cyan-300 text-sm font-medium">{crop.name}</p>
              {crop.unlock_cost > 0 && (
                <span className="text-amber-400 text-[9px] bg-amber-900/30 px-1 rounded">
                  {crop.unlock_cost} SD
                </span>
              )}
            </div>
            <p className="text-slate-500 text-[10px]">
              {crop.grow_time_minutes}min grow | {crop.decay_minutes}min decay
            </p>
            <p className="text-slate-600 text-[9px] truncate">{crop.description}</p>
          </div>
          <div className="text-right flex-shrink-0">
            <div className="text-yellow-400/80 font-mono text-sm">{crop.points} pts</div>
            <div className="text-amber-500/60 font-mono text-[10px]">{crop.sand_dollar_yield} SD</div>
            {crop.plant_cost > 0 && (
              <div className="text-slate-500 text-[9px]">Cost: {crop.plant_cost}</div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
