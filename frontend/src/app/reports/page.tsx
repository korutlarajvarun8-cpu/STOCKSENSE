"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { BarChart3, AlertTriangle, TrendingUp, Download, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function ReportsPage() {
  const { data: overview, isLoading: loadingOverview } = useQuery({
    queryKey: ["reports", "overview"],
    queryFn: async () => (await api.get("/reports/inventory-overview")).data,
  });

  const { data: lowStock, isLoading: loadingLow } = useQuery({
    queryKey: ["reports", "low-stock"],
    queryFn: async () => (await api.get("/reports/low-stock")).data,
  });

  const { data: movement, isLoading: loadingMove } = useQuery({
    queryKey: ["reports", "movement"],
    queryFn: async () => (await api.get("/reports/stock-movement?days=30")).data,
  });

  if (loadingOverview || loadingLow || loadingMove) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Reports & Analytics</h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Exportable insights on your inventory health and movements.
          </p>
        </div>
        <div className="mt-4 sm:mt-0 flex space-x-3">
          <button className="inline-flex items-center px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-lg shadow-sm text-sm font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
            <Download className="mr-2 h-4 w-4" />
            Export CSV
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500 flex items-center">
              <BarChart3 className="w-4 h-4 mr-2" />
              Inventory Valuation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              ${overview?.total_value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Across {overview?.total_products} tracked products
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500 flex items-center">
              <AlertTriangle className="w-4 h-4 mr-2 text-amber-500" />
              Low Stock Items
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {lowStock?.total || 0}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Products below reorder threshold
            </p>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500 flex items-center">
              <TrendingUp className="w-4 h-4 mr-2 text-blue-500" />
              30-Day Movement
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {movement?.incoming + movement?.outgoing}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Total units moved (In & Out)
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle>Low Stock Alerts</CardTitle>
            <CardDescription>Items that need immediate replenishment.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
                <thead>
                  <tr>
                    <th className="py-2 text-left text-xs font-medium text-slate-500 uppercase">Product</th>
                    <th className="py-2 text-left text-xs font-medium text-slate-500 uppercase">Available</th>
                    <th className="py-2 text-left text-xs font-medium text-slate-500 uppercase">Reorder Lvl</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                  {lowStock?.items.length === 0 ? (
                    <tr><td colSpan={3} className="py-4 text-center text-sm text-slate-500">No low stock items.</td></tr>
                  ) : (
                    lowStock?.items.slice(0, 5).map((item: any) => (
                      <tr key={item.id}>
                        <td className="py-3 text-sm font-medium text-slate-900 dark:text-white">{item.name}</td>
                        <td className="py-3 text-sm text-red-600 font-bold">{item.available}</td>
                        <td className="py-3 text-sm text-slate-500">{item.reorder_level}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200 dark:border-slate-800 shadow-sm">
          <CardHeader>
            <CardTitle>Movement Breakdown (30 Days)</CardTitle>
            <CardDescription>Volume of stock passing through operations.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-900 rounded-lg">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Incoming (Receipts)</span>
                <span className="text-sm font-bold text-emerald-600">+{movement?.incoming} units</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-900 rounded-lg">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Outgoing (Deliveries)</span>
                <span className="text-sm font-bold text-blue-600">-{movement?.outgoing} units</span>
              </div>
              <div className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-900 rounded-lg">
                <span className="text-sm font-medium text-slate-700 dark:text-slate-300">Adjustments</span>
                <span className="text-sm font-bold text-amber-600">{movement?.adjustments} units</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
