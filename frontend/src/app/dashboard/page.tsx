"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { 
  Package, 
  AlertTriangle, 
  ArrowDownToLine, 
  ArrowUpFromLine,
  TrendingUp,
  BoxSelect,
  Loader2
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

function StatCard({ 
  title, 
  value, 
  icon: Icon, 
  trend, 
  trendUp, 
  colorClass 
}: { 
  title: string; 
  value: string | number; 
  icon: any; 
  trend?: string; 
  trendUp?: boolean;
  colorClass: string;
}) {
  return (
    <div className="bg-white dark:bg-slate-950 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-slate-500 dark:text-slate-400 text-sm font-medium">{title}</h3>
        <div className={`p-2 rounded-lg ${colorClass}`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
      <div className="flex items-baseline space-x-2">
        <h2 className="text-3xl font-bold text-slate-900 dark:text-white">{value}</h2>
        {trend && (
          <span className={`text-xs font-medium ${trendUp ? 'text-emerald-600' : 'text-red-600'}`}>
            {trendUp ? '↑' : '↓'} {trend}
          </span>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({
    queryKey: ["dashboard"],
    queryFn: async () => {
      const res = await api.get("/dashboard");
      return res.data;
    },
  });

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  const kpis = data?.kpis || {};
  const recentMovements = data?.recent_movements || [];
  const chartData = data?.movement_chart || [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Dashboard Overview</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Real-time insights into your inventory and operations.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Total On Hand"
          value={kpis.total_on_hand || 0}
          icon={Package}
          colorClass="bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
        />
        <StatCard
          title="Inventory Value"
          value={`$${(kpis.total_inventory_value || 0).toLocaleString()}`}
          icon={TrendingUp}
          colorClass="bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
        />
        <StatCard
          title="Low Stock Alerts"
          value={kpis.low_stock_count || 0}
          icon={AlertTriangle}
          colorClass={kpis.low_stock_count > 0 ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400" : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400"}
        />
        <StatCard
          title="Pending Operations"
          value={(kpis.pending_receipts || 0) + (kpis.pending_deliveries || 0)}
          icon={ArrowDownToLine}
          colorClass="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Chart */}
        <div className="lg:col-span-2 bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm p-6">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Stock Movements (30 Days)</h3>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorIncoming" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorOutgoing" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#334155" opacity={0.2} />
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} dy={10} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#64748b' }} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', border: 'none', borderRadius: '8px', color: '#f8fafc' }}
                  itemStyle={{ fontSize: '14px' }}
                />
                <Area type="monotone" dataKey="incoming" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorIncoming)" />
                <Area type="monotone" dataKey="outgoing" stroke="#f43f5e" strokeWidth={2} fillOpacity={1} fill="url(#colorOutgoing)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Movements */}
        <div className="bg-white dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm p-6 flex flex-col">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Recent Activity</h3>
          <div className="flex-1 overflow-auto">
            <div className="space-y-4">
              {recentMovements.length === 0 ? (
                <p className="text-slate-500 text-sm text-center py-8">No recent activity</p>
              ) : (
                recentMovements.map((move: any) => (
                  <div key={move.id} className="flex items-start p-3 hover:bg-slate-50 dark:hover:bg-slate-900/50 rounded-lg transition-colors border border-transparent hover:border-slate-100 dark:hover:border-slate-800">
                    <div className={`mt-0.5 p-2 rounded-full ${
                      move.type === 'RECEIPT' || move.type.includes('IN') 
                        ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30' 
                        : move.type === 'DELIVERY' || move.type.includes('OUT')
                          ? 'bg-red-100 text-red-600 dark:bg-red-900/30'
                          : 'bg-blue-100 text-blue-600 dark:bg-blue-900/30'
                    }`}>
                      {move.type === 'RECEIPT' || move.type.includes('IN') ? (
                        <ArrowDownToLine className="w-4 h-4" />
                      ) : move.type === 'DELIVERY' || move.type.includes('OUT') ? (
                        <ArrowUpFromLine className="w-4 h-4" />
                      ) : (
                        <BoxSelect className="w-4 h-4" />
                      )}
                    </div>
                    <div className="ml-3 flex-1">
                      <div className="flex justify-between items-start">
                        <p className="text-sm font-medium text-slate-900 dark:text-white line-clamp-1">{move.product}</p>
                        <span className={`text-xs font-bold whitespace-nowrap ml-2 ${
                          parseFloat(move.quantity) > 0 ? 'text-emerald-600' : 'text-red-600'
                        }`}>
                          {parseFloat(move.quantity) > 0 ? '+' : ''}{move.quantity}
                        </span>
                      </div>
                      <div className="flex justify-between items-center mt-1">
                        <p className="text-xs text-slate-500">{move.type} • {move.reference}</p>
                        <p className="text-xs text-slate-400">{new Date(move.date).toLocaleDateString()}</p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
