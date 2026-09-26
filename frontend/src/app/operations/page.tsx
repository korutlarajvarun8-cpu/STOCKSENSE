"use client";

import Link from "next/link";
import { 
  ArrowDownToLine, 
  ArrowUpFromLine, 
  ArrowRightLeft, 
  Scale, 
  ShoppingCart,
  TrendingDown
} from "lucide-react";

const OPERATIONS = [
  {
    title: "Receipts",
    description: "Receive stock from suppliers against purchase orders.",
    icon: ArrowDownToLine,
    href: "/operations/receipts",
    color: "text-emerald-600 dark:text-emerald-400",
    bg: "bg-emerald-100 dark:bg-emerald-900/30",
  },
  {
    title: "Deliveries",
    description: "Pick, pack, and deliver stock to customers for sales orders.",
    icon: ArrowUpFromLine,
    href: "/operations/deliveries",
    color: "text-red-600 dark:text-red-400",
    bg: "bg-red-100 dark:bg-red-900/30",
  },
  {
    title: "Transfers",
    description: "Move inventory between warehouses and locations.",
    icon: ArrowRightLeft,
    href: "/operations/transfers",
    color: "text-blue-600 dark:text-blue-400",
    bg: "bg-blue-100 dark:bg-blue-900/30",
  },
  {
    title: "Inventory Adjustments",
    description: "Correct stock levels due to shrinkage, damage, or recounts.",
    icon: Scale,
    href: "/operations/adjustments",
    color: "text-amber-600 dark:text-amber-400",
    bg: "bg-amber-100 dark:bg-amber-900/30",
  },
];

const PURCHASING = [
  {
    title: "Purchase Orders",
    description: "Create and manage orders to suppliers.",
    icon: ShoppingCart,
    href: "/purchasing/orders",
    color: "text-indigo-600 dark:text-indigo-400",
    bg: "bg-indigo-100 dark:bg-indigo-900/30",
  },
  {
    title: "Sales Orders",
    description: "Manage customer orders and reserve stock.",
    icon: TrendingDown,
    href: "/sales/orders",
    color: "text-fuchsia-600 dark:text-fuchsia-400",
    bg: "bg-fuchsia-100 dark:bg-fuchsia-900/30",
  },
];

function ActionCard({ item }: { item: typeof OPERATIONS[0] }) {
  const Icon = item.icon;
  return (
    <Link
      href={item.href}
      className="group bg-white dark:bg-slate-950 rounded-xl p-6 border border-slate-200 dark:border-slate-800 shadow-sm hover:shadow-md transition-all hover:border-blue-200 dark:hover:border-blue-900"
    >
      <div className="flex items-center space-x-4">
        <div className={`p-3 rounded-xl ${item.bg} group-hover:scale-110 transition-transform`}>
          <Icon className={`w-6 h-6 ${item.color}`} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
            {item.title}
          </h3>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            {item.description}
          </p>
        </div>
      </div>
    </Link>
  );
}

export default function OperationsPage() {
  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Operations Hub</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Centralized management for all inventory movements and orders.
        </p>
      </div>

      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Stock Movements</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {OPERATIONS.map((item) => (
            <ActionCard key={item.href} item={item} />
          ))}
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold text-slate-900 dark:text-white mb-4">Orders & Commercial</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {PURCHASING.map((item) => (
            <ActionCard key={item.href} item={item} />
          ))}
        </div>
      </section>
    </div>
  );
}
