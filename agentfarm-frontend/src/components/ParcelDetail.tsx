import { Parcel, CropInfo } from '../lib/api';

interface ParcelDetailProps {
  parcel: Parcel;
  crops: CropInfo[];
  onClose: () => void;
}

const STAGE_LABELS: Record<string, string> = {
  empty: 'Empty',
  seedling: 'Seedling',
  sprouting: 'Sprouting',
  growing: 'Growing',
  mature: 'Ready to Harvest!',
  dead: 'Eaten by Algae!',
};

export default function ParcelDetail({ parcel, crops, onClose }: ParcelDetailProps) {
  const cropMap = new Map(crops.map(c => [c.key, c]));
  const activePlots = parcel.plots.filter(p => p.crop_type);

  return (
    <div className="bg-slate-900/95 border border-cyan-500/30 rounded-xl p-4 backdrop-blur-sm">
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="text-cyan-300 font-bold text-lg">
            Parcel ({parcel.x}, {parcel.y})
          </h3>
          {parcel.owner_name ? (
            <p className="text-cyan-500/70 text-sm">
              Owned by <span className="text-cyan-300">{parcel.owner_name}</span>
            </p>
          ) : (
            <p className="text-slate-500 text-sm italic">
              Unclaimed waters {parcel.price > 0 ? `- ${parcel.price} Sand Dollars` : '- FREE'}
            </p>
          )}
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-cyan-300 text-lg font-bold w-6 h-6 flex items-center justify-center"
        >
          x
        </button>
      </div>

      {/* 3x3 Plot Grid */}
      <div className="grid grid-cols-3 gap-1 mb-3">
        {parcel.plots.map(plot => {
          const crop = plot.crop_type ? cropMap.get(plot.crop_type) : null;
          const isEmpty = plot.growth_stage === 'empty';

          return (
            <div
              key={`${plot.local_x}-${plot.local_y}`}
              className={`
                aspect-square rounded-lg border flex flex-col items-center justify-center p-1 text-center
                ${isEmpty
                  ? 'border-slate-700/50 bg-slate-800/30'
                  : plot.growth_stage === 'mature'
                    ? 'border-yellow-400/50 bg-yellow-900/20 animate-pulse'
                    : 'border-cyan-500/30 bg-cyan-900/20'
                }
              `}
            >
              {crop ? (
                <>
                  <span className="text-xl">{plot.is_dead ? '💀' : crop.emoji}</span>
                  <span className={`text-[9px] leading-tight mt-0.5 ${
                    plot.is_dead ? 'text-red-400' : plot.growth_stage === 'mature' ? 'text-yellow-400' : 'text-cyan-400/80'
                  }`}>
                    {STAGE_LABELS[plot.is_dead ? 'dead' : plot.growth_stage] || plot.growth_stage}
                  </span>
                  <div className="w-full mt-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        plot.is_dead ? 'bg-red-500' : plot.growth_stage === 'mature' ? 'bg-yellow-400' : 'bg-cyan-400'
                      }`}
                      style={{ width: `${plot.progress_pct}%` }}
                    />
                  </div>
                  {plot.growth_stage === 'mature' && !plot.is_dead && (
                    <div className="w-full mt-0.5 h-1 bg-slate-700 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          plot.health > 0.6 ? 'bg-green-400' : plot.health > 0.3 ? 'bg-yellow-400' : 'bg-red-400'
                        }`}
                        style={{ width: `${Math.round(plot.health * 100)}%` }}
                      />
                    </div>
                  )}
                  <span className="text-[8px] text-slate-500">{plot.progress_pct}%{plot.growth_stage === 'mature' && !plot.is_dead ? ` HP:${Math.round(plot.health * 100)}%` : ''}</span>
                </>
              ) : (
                <span className="text-slate-600 text-xs">~</span>
              )}
            </div>
          );
        })}
      </div>

      {/* Summary */}
      {activePlots.length > 0 && (
        <div className="text-xs text-slate-400 space-y-1">
          {activePlots.map(plot => {
            const crop = cropMap.get(plot.crop_type!);
            return (
              <div key={`${plot.local_x}-${plot.local_y}`} className="flex items-center gap-2">
                <span>{crop?.emoji}</span>
                <span className="text-cyan-400">{crop?.name}</span>
                <span className="text-slate-500">
                  {plot.watered_at ? ' (watered)' : ''}
                </span>
                <span className="ml-auto text-cyan-500">{plot.progress_pct}%</span>
              </div>
            );
          })}
        </div>
      )}

      {!parcel.owner_id && (
        <div className="text-center mt-2">
          <p className="text-slate-500 text-sm italic">
            This parcel is waiting for an agent to claim it...
          </p>
          <p className="text-amber-400/70 text-xs mt-1">
            {parcel.price > 0 ? `Price: ${parcel.price} Sand Dollars` : 'FREE to claim!'}
          </p>
        </div>
      )}
    </div>
  );
}
