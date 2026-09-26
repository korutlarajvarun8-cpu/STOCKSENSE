"use client";

import { useAuthStore } from "@/lib/auth";
import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";
import {
  Bell, Search, Menu, LogOut, Settings, ArrowRightLeft, Package,
  LayoutDashboard, Check, Users, Truck, ShoppingCart, BarChart3,
  Layers, Hash, RefreshCcw, Building2, ClipboardList
} from "lucide-react";
import { cn } from "@/lib/utils";
import { AIAssistant } from "@/components/AIAssistant";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";

const NAV_GROUPS = [
  {
    label: null,
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
    ]
  },
  {
    label: "Inventory",
    items: [
      { href: "/products", label: "Products", icon: Package },
      { href: "/inventory/batches", label: "Batches & Lots", icon: Layers },
      { href: "/inventory/serials", label: "Serial Numbers", icon: Hash },
      { href: "/inventory/reorder-rules", label: "Reorder Rules", icon: RefreshCcw },
    ]
  },
  {
    label: "Operations",
    items: [
      { href: "/operations/receipts", label: "Receipts", icon: ClipboardList },
      { href: "/operations/deliveries", label: "Deliveries", icon: Truck },
      { href: "/operations/transfers", label: "Transfers", icon: ArrowRightLeft },
      { href: "/operations/adjustments", label: "Adjustments", icon: Settings },
    ]
  },
  {
    label: "Commercial",
    items: [
      { href: "/purchasing/orders", label: "Purchase Orders", icon: ShoppingCart },
      { href: "/sales/orders", label: "Sales Orders", icon: BarChart3 },
      { href: "/suppliers", label: "Suppliers", icon: Building2 },
      { href: "/customers", label: "Customers", icon: Users },
    ]
  },
  {
    label: "Analytics",
    items: [
      { href: "/reports", label: "Reports", icon: BarChart3 },
    ]
  },
  {
    label: "Admin",
    items: [
      { href: "/settings", label: "Settings", icon: Settings },
    ]
  },
];

export function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isAuthenticated, checkAuth, logout } = useAuthStore();
  const router = useRouter();
  const pathname = usePathname();
  const queryClient = useQueryClient();

  useEffect(() => {
    // Basic auth check
    if (!isAuthenticated && pathname !== "/login") {
      router.push("/login");
    }
  }, [isAuthenticated, pathname, router]);

  // Real-time WebSocket setup
  useEffect(() => {
    if (!isAuthenticated) return;
    
    // Check if window is defined (browser env)
    if (typeof window === 'undefined') return;
    
    const token = localStorage.getItem("auth_token");
    if (!token) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/api/ws?token=${token}`;
    
    let ws: WebSocket;
    
    try {
      ws = new WebSocket(wsUrl);
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // When a real-time event occurs, invalidate relevant queries
          if (data.type?.includes("RECEIPT") || data.type?.includes("DELIVERY") || data.type?.includes("TRANSFER")) {
            queryClient.invalidateQueries({ queryKey: ["dashboard"] });
            queryClient.invalidateQueries({ queryKey: ["reports"] });
          }
          // Always refresh notifications
          queryClient.invalidateQueries({ queryKey: ["notifications"] });
        } catch (e) {
          console.error("WS parse error", e);
        }
      };
    } catch (e) {
      console.error("WS connect error", e);
    }

    return () => {
      if (ws) ws.close();
    };
  }, [isAuthenticated, queryClient]);

  // Fetch unread notifications
  const { data: notifs } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: async () => (await api.get("/notifications?unread_only=true")).data,
    enabled: isAuthenticated,
    refetchInterval: 60000, // Poll every minute as fallback
  });

  const markAllRead = useMutation({
    mutationFn: async () => await api.post("/notifications/read-all"),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
    },
  });

  if (!isAuthenticated && pathname === "/login") {
    return <>{children}</>;
  }

  if (!isAuthenticated) {
    return null; // Or a loading spinner
  }

  const unreadCount = notifs?.unread_count || 0;
  const notifications = notifs?.items || [];

  return (
    <div className="flex h-screen bg-transparent">
      {/* Sidebar */}
      <aside className="w-64 glass border-r border-slate-200/50 dark:border-slate-800/50 flex flex-col hidden md:flex z-20">
        <div className="h-16 flex items-center px-6 border-b border-slate-200/50 dark:border-slate-800/50">
          <span className="text-xl font-extrabold tracking-tight premium-gradient-text">
            StockSense
          </span>
        </div>
        
        <nav className="flex-1 py-4 px-3 overflow-y-auto">
          {NAV_GROUPS.map((group, gi) => (
            <div key={gi} className={gi > 0 ? "mt-4" : ""}>
              {group.label && (
                <p className="px-3 mb-1 text-[10px] font-semibold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
                  {group.label}
                </p>
              )}
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={cn(
                        "flex items-center px-3 py-2 rounded-xl text-sm font-medium transition-all duration-300",
                        isActive
                          ? "bg-blue-50/80 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300 shadow-sm"
                          : "text-slate-600 hover:bg-slate-100/80 dark:text-slate-400 dark:hover:bg-slate-800/50 hover:translate-x-1"
                      )}
                    >
                      <Icon className={cn("mr-3 h-4 w-4 flex-shrink-0", isActive ? "text-blue-700 dark:text-blue-400" : "text-slate-400")} />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-200/50 dark:border-slate-800/50 backdrop-blur-md">
          <div className="flex items-center mb-4 px-2">
            <div className="h-8 w-8 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-blue-700 dark:text-blue-300 font-bold">
              {user?.full_name?.charAt(0) || "U"}
            </div>
            <div className="ml-3 truncate">
              <p className="text-sm font-medium text-slate-900 dark:text-white truncate">{user?.full_name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400 truncate">{user?.role}</p>
            </div>
          </div>
          <button
            onClick={() => {
              logout();
              router.push("/login");
            }}
            className="flex w-full items-center px-3 py-2 text-sm font-medium text-red-600 rounded-lg hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
          >
            <LogOut className="mr-3 h-5 w-5" />
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 overflow-hidden bg-transparent">
        {/* Header */}
        <header className="h-16 glass border-b border-slate-200/50 dark:border-slate-800/50 flex items-center justify-between px-4 sm:px-6 z-10 sticky top-0">
          <div className="flex items-center flex-1">
            <button className="md:hidden mr-4 text-slate-500 hover:text-slate-700">
              <Menu className="h-6 w-6" />
            </button>
            <div className="max-w-md w-full relative hidden sm:block">
              <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                <Search className="h-4 w-4 text-slate-400" />
              </div>
              <input
                type="text"
                placeholder="Search products, orders (Ctrl+K)..."
                className="block w-full pl-10 pr-3 py-2 border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-900 text-sm placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              />
            </div>
          </div>
          <div className="flex items-center space-x-4">
            <Popover>
              <PopoverTrigger asChild>
                <button className="relative p-2 text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 transition-colors">
                  <Bell className="h-5 w-5" />
                  {unreadCount > 0 && (
                    <span className="absolute top-1.5 right-1.5 flex h-4 w-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white ring-2 ring-white dark:ring-slate-950">
                      {unreadCount > 9 ? '9+' : unreadCount}
                    </span>
                  )}
                </button>
              </PopoverTrigger>
              <PopoverContent align="end" className="w-80 p-0">
                <div className="flex items-center justify-between border-b px-4 py-3">
                  <h4 className="font-semibold text-sm">Notifications</h4>
                  {unreadCount > 0 && (
                    <button 
                      onClick={() => markAllRead.mutate()}
                      className="text-xs text-blue-600 hover:text-blue-800 dark:text-blue-400 font-medium flex items-center"
                    >
                      <Check className="h-3 w-3 mr-1" />
                      Mark all read
                    </button>
                  )}
                </div>
                <ScrollArea className="h-[300px]">
                  {notifications.length === 0 ? (
                    <div className="flex h-full items-center justify-center p-4 text-sm text-slate-500">
                      No new notifications
                    </div>
                  ) : (
                    <div className="flex flex-col">
                      {notifications.map((n: any) => (
                        <div key={n.id} className="border-b last:border-0 p-4 hover:bg-slate-50 dark:hover:bg-slate-900/50 transition-colors">
                          <p className="text-sm font-medium text-slate-900 dark:text-slate-100">{n.title}</p>
                          <p className="text-xs text-slate-500 mt-1 line-clamp-2">{n.message}</p>
                          <p className="text-[10px] text-slate-400 mt-2">
                            {new Date(n.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </ScrollArea>
              </PopoverContent>
            </Popover>
          </div>
        </header>
        {/* Page Content */}
        <div className="flex-1 overflow-auto p-4 sm:p-6 lg:p-8 animate-fade-in">
          <div className="mx-auto max-w-7xl animate-slide-up">
            {children}
          </div>
        </div>
        <AIAssistant />
      </main>
    </div>
  );
}
