/**
 * Sparkline — handoff: 64×24, 1.5px çizgi, yuvarlatılmış uçlar, %80 opaklık.
 *
 * Eksen ve etiket yok: kartın büyük rakamının yönünü gösterir, değer okutmaz. Tek nokta
 * varsa çizilmez — bir noktadan trend çıkarmak yanıltıcı olurdu.
 */

export function Sparkline({
  values,
  color,
  width = 64,
  height = 24,
}: {
  values: number[];
  color: string;
  width?: number;
  height?: number;
}) {
  if (values.length < 2) return null;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const padding = 2;
  const stepX = (width - padding * 2) / (values.length - 1);

  const points = values
    .map((value, index) => {
      const x = padding + index * stepX;
      const y = height - padding - ((value - min) / span) * (height - padding * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity={0.8}
      />
    </svg>
  );
}
