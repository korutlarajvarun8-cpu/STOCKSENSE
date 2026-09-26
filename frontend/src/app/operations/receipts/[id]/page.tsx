"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft, CheckCircle2, Clock, MapPin, Package, Save, ShieldAlert, FileCheck } from "lucide-react";
import Link from "next/link";

export default function ReceiptDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = params.id as string;

  const { data: receipt, isLoading } = useQuery({
    queryKey: ["receipt", id],
    queryFn: async () => {
      const res = await api.get(`/receipts/${id}`);
      return res.data;
    },
  });

  const validateMutation = useMutation({
    mutationFn: async () => {
      const res = await api.post(`/receipts/${id}/validate`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["receipt", id] });
      queryClient.invalidateQueries({ queryKey: ["receipts"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  if (isLoading) {
    return <div className="p-8 text-center text-slate-500">Loading receipt details...</div>;
  }

  if (!receipt) {
    return <div className="p-8 text-center text-red-500">Receipt not found.</div>;
  }

  const isDone = receipt.status === 'DONE';

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex items-center space-x-4 mb-2">
        <Link href="/operations/receipts" className="p-2 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
          <ArrowLeft className="w-5 h-5 text-slate-600 dark:text-slate-400" />
        </Link>
        <div className="flex items-center space-x-3">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">
            {receipt.receipt_number}
          </h1>
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
            isDone ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"
          }`}>
            {receipt.status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2 space-y-6">
          <div className="bg-white dark:bg-slate-950 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex justify-between items-center">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Operations</h2>
              {!isDone && (
                <button
                  onClick={() => validateMutation.mutate()}
                  disabled={validateMutation.isPending}
                  className="inline-flex items-center px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                >
                  <FileCheck className="w-4 h-4 mr-2" />
                  {validateMutation.isPending ? "Validating..." : "Validate Receipt"}
                </button>
              )}
            </div>
            
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
                <thead className="bg-slate-50 dark:bg-slate-900/50">
                  <tr>
                    <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase">Product</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">Expected</th>
                    <th scope="col" className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase">Done</th>
                  </tr>
                </thead>
                <tbody className="bg-white dark:bg-slate-950 divide-y divide-slate-200 dark:divide-slate-800">
                  {receipt.items.map((item: any) => (
                    <tr key={item.id}>
                      <td className="px-6 py-4">
                        <div className="text-sm font-medium text-slate-900 dark:text-white">{item.product_name}</div>
                        <div className="text-xs text-slate-500">{item.product_sku}</div>
                      </td>
                      <td className="px-6 py-4 text-right text-sm text-slate-600 dark:text-slate-400">
                        {item.quantity_expected}
                      </td>
                      <td className="px-6 py-4 text-right">
                        {!isDone ? (
                          <input 
                            type="number" 
                            defaultValue={item.quantity_received || item.quantity_expected}
                            className="w-24 px-2 py-1 text-right border border-slate-300 dark:border-slate-700 rounded-md bg-white dark:bg-slate-900 text-sm focus:ring-emerald-500 focus:border-emerald-500"
                            readOnly // In a real app we'd add state management to update quantities before validation
                          />
                        ) : (
                          <span className="text-sm font-bold text-emerald-600 dark:text-emerald-400">
                            {item.quantity_received}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!isDone && (
              <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border-t border-amber-200 dark:border-amber-800 text-sm text-amber-800 dark:text-amber-400 flex items-start">
                <ShieldAlert className="w-5 h-5 mr-2 flex-shrink-0" />
                <p>Validating this receipt will immediately increment the stock on hand in the destination location. This operation creates an immutable stock ledger entry and cannot be silently deleted.</p>
              </div>
            )}
            {validateMutation.isError && (
              <div className="p-4 bg-red-50 text-red-600 text-sm border-t border-red-200">
                {(validateMutation.error as any).response?.data?.detail || "Validation failed."}
              </div>
            )}
            {validateMutation.isSuccess && (
              <div className="p-4 bg-emerald-50 text-emerald-600 text-sm border-t border-emerald-200 flex items-center">
                <CheckCircle2 className="w-5 h-5 mr-2" />
                Receipt validated successfully. Inventory has been updated.
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6">
          <div className="bg-white dark:bg-slate-950 rounded-xl shadow-sm border border-slate-200 dark:border-slate-800 p-6">
            <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400 mb-4 uppercase tracking-wider">Logistics Info</h3>
            
            <div className="space-y-4">
              <div className="flex items-start">
                <MapPin className="w-5 h-5 text-slate-400 mr-3 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">Destination Location</p>
                  <p className="text-sm text-slate-500">{receipt.warehouse_name}</p>
                  <p className="text-xs text-slate-400">{receipt.destination_location_name}</p>
                </div>
              </div>

              <div className="flex items-start">
                <Package className="w-5 h-5 text-slate-400 mr-3 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">Supplier</p>
                  <p className="text-sm text-slate-500">{receipt.supplier_name || 'No supplier linked'}</p>
                </div>
              </div>

              <div className="flex items-start">
                <Clock className="w-5 h-5 text-slate-400 mr-3 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-slate-900 dark:text-white">Scheduled Date</p>
                  <p className="text-sm text-slate-500">
                    {receipt.scheduled_date ? new Date(receipt.scheduled_date).toLocaleDateString() : 'None'}
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
