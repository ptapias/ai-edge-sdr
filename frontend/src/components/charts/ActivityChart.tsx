import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts'

interface ActivityData {
  date: string
  invitations: number
  successful_invitations: number
  connections: number
}

export default function ActivityChart({ timeline }: { timeline: ActivityData[] }) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
        No activity data yet
      </div>
    )
  }

  // Format dates for display
  const formattedData = timeline.map((d) => ({
    ...d,
    label: new Date(d.date).toLocaleDateString('en', { month: 'short', day: 'numeric' }),
  }))

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={formattedData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f3f4f6" />
        <XAxis
          dataKey="label"
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          tickLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#9ca3af' }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{ borderRadius: '8px', border: '1px solid #e5e7eb', fontSize: '12px' }}
        />
        <Legend
          verticalAlign="bottom"
          height={36}
          formatter={(value) => <span className="text-xs text-gray-600">{value}</span>}
        />
        <Line
          type="monotone"
          dataKey="invitations"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
          name="Invitations"
        />
        <Line
          type="monotone"
          dataKey="connections"
          stroke="#10b981"
          strokeWidth={2}
          dot={false}
          name="Connections"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
