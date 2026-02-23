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
          <div className="flex-1">
            <p className="text-cyan-300 text-sm font-medium">{crop.name}</p>
            <p className="text-slate-500 text-[10px]">
              {crop.grow_time_minutes}min grow time
            </p>
          </div>
          <div className="text-right">
            <span className="text-yellow-400/80 font-mono text-sm">{crop.points}</span>
            <span className="text-slate-600 text-[10px] ml-1">pts</span>
          </div>
        </div>
      ))}
    </div>
  );
}
