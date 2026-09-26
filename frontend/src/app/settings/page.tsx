"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth";
import {
  Settings, User, Shield, Bell, Database, Key,
  Save, Loader2, CheckCircle2, AlertTriangle
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

const ROLE_COLORS: Record<string, string> = {
  ADMIN: "bg-red-100 text-red-800",
  INVENTORY_MANAGER: "bg-blue-100 text-blue-800",
  WAREHOUSE_STAFF: "bg-emerald-100 text-emerald-800",
  VIEWER: "bg-slate-100 text-slate-800",
};

export default function SettingsPage() {
  const { user } = useAuthStore();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState("profile");
  const [saved, setSaved] = useState(false);

  const { data: users, isLoading: loadingUsers } = useQuery({
    queryKey: ["users"],
    queryFn: async () => (await api.get("/users")).data,
    enabled: user?.role === "ADMIN",
  });

  const updateUser = useMutation({
    mutationFn: async ({ id, data }: { id: string; data: any }) =>
      await api.put(`/users/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  const tabs = [
    { id: "profile", label: "Profile", icon: User },
    { id: "users", label: "User Management", icon: Shield, adminOnly: true },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "system", label: "System Info", icon: Database },
  ].filter(t => !t.adminOnly || user?.role === "ADMIN");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Settings</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage your account, users, and system preferences.
        </p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar Tabs */}
        <aside className="w-52 flex-shrink-0">
          <nav className="space-y-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left ${
                    activeTab === tab.id
                      ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                      : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800/50"
                  }`}
                >
                  <Icon className="mr-3 h-4 w-4" />
                  {tab.label}
                </button>
              );
            })}
          </nav>
        </aside>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-6">
          {/* Profile Tab */}
          {activeTab === "profile" && (
            <Card className="border-slate-200 dark:border-slate-800">
              <CardHeader>
                <CardTitle>My Profile</CardTitle>
                <CardDescription>Your account information and role.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center space-x-4">
                  <div className="h-16 w-16 rounded-full bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-blue-700 dark:text-blue-300 text-2xl font-bold">
                    {user?.full_name?.charAt(0) || "U"}
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-slate-900 dark:text-white">{user?.full_name}</p>
                    <p className="text-sm text-slate-500">{user?.email}</p>
                    <span className={`mt-1 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${ROLE_COLORS[user?.role || "VIEWER"] || ROLE_COLORS.VIEWER}`}>
                      {user?.role?.replace("_", " ")}
                    </span>
                  </div>
                </div>
                <div className="border-t border-slate-200 dark:border-slate-800 pt-4">
                  <p className="text-sm text-slate-500 dark:text-slate-400">
                    To update your profile details, contact your system administrator.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {/* User Management Tab */}
          {activeTab === "users" && user?.role === "ADMIN" && (
            <Card className="border-slate-200 dark:border-slate-800">
              <CardHeader>
                <CardTitle>User Management</CardTitle>
                <CardDescription>Manage system users and their roles.</CardDescription>
              </CardHeader>
              <CardContent>
                {saved && (
                  <div className="mb-4 flex items-center p-3 bg-emerald-50 dark:bg-emerald-900/20 rounded-lg text-emerald-700 dark:text-emerald-400 text-sm">
                    <CheckCircle2 className="mr-2 h-4 w-4" /> Changes saved successfully.
                  </div>
                )}
                {loadingUsers ? (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-800">
                      <thead className="bg-slate-50 dark:bg-slate-900/50">
                        <tr>
                          <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">User</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Role</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Status</th>
                          <th className="px-4 py-3 text-left text-xs font-medium text-slate-500 uppercase">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-800">
                        {users?.map((u: any) => (
                          <tr key={u.id} className="hover:bg-slate-50 dark:hover:bg-slate-900/40">
                            <td className="px-4 py-3">
                              <p className="text-sm font-medium text-slate-900 dark:text-white">{u.full_name}</p>
                              <p className="text-xs text-slate-500">{u.email}</p>
                            </td>
                            <td className="px-4 py-3">
                              <select
                                defaultValue={u.role}
                                onChange={(e) => updateUser.mutate({ id: u.id, data: { role: e.target.value } })}
                                className="text-xs border border-slate-300 dark:border-slate-700 rounded px-2 py-1 bg-white dark:bg-slate-900"
                              >
                                <option value="ADMIN">Admin</option>
                                <option value="INVENTORY_MANAGER">Inventory Manager</option>
                                <option value="WAREHOUSE_STAFF">Warehouse Staff</option>
                                <option value="VIEWER">Viewer</option>
                              </select>
                            </td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                u.is_active ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"
                              }`}>
                                {u.is_active ? "Active" : "Inactive"}
                              </span>
                            </td>
                            <td className="px-4 py-3">
                              <button
                                onClick={() => updateUser.mutate({ id: u.id, data: { is_active: !u.is_active } })}
                                className="text-xs text-blue-600 hover:underline dark:text-blue-400"
                              >
                                {u.is_active ? "Deactivate" : "Activate"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Notifications Tab */}
          {activeTab === "notifications" && (
            <Card className="border-slate-200 dark:border-slate-800">
              <CardHeader>
                <CardTitle>Notification Preferences</CardTitle>
                <CardDescription>Control which events trigger notifications.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {[
                  { label: "Low Stock Alerts", desc: "Notified when a product drops below reorder level", defaultOn: true },
                  { label: "Pending Receipts", desc: "Daily digest of unvalidated receipts", defaultOn: true },
                  { label: "Pending Deliveries", desc: "Daily digest of pending delivery validations", defaultOn: false },
                  { label: "Expiry Warnings", desc: "Alert when batch items approach expiry", defaultOn: true },
                  { label: "AI Anomalies", desc: "Unusual stock movement detections", defaultOn: false },
                ].map((pref) => (
                  <div key={pref.label} className="flex items-center justify-between py-3 border-b border-slate-100 dark:border-slate-800 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-slate-900 dark:text-white">{pref.label}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{pref.desc}</p>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" defaultChecked={pref.defaultOn} className="sr-only peer" />
                      <div className="w-11 h-6 bg-slate-200 peer-focus:ring-2 peer-focus:ring-blue-300 rounded-full peer dark:bg-slate-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    </label>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* System Tab */}
          {activeTab === "system" && (
            <Card className="border-slate-200 dark:border-slate-800">
              <CardHeader>
                <CardTitle>System Information</CardTitle>
                <CardDescription>Technical details about your StockSense instance.</CardDescription>
              </CardHeader>
              <CardContent>
                <dl className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {[
                    { label: "Version", value: "StockSense v1.0.0" },
                    { label: "Environment", value: "Production" },
                    { label: "Database", value: "PostgreSQL 16" },
                    { label: "Cache", value: "Redis 7" },
                    { label: "API", value: "FastAPI + SQLAlchemy" },
                    { label: "Frontend", value: "Next.js 14 (App Router)" },
                    { label: "Auth", value: "JWT (Access + Refresh)" },
                    { label: "Real-time", value: "WebSocket (FastAPI)" },
                  ].map((item) => (
                    <div key={item.label} className="flex flex-col p-3 bg-slate-50 dark:bg-slate-900 rounded-lg">
                      <dt className="text-xs text-slate-500 uppercase tracking-wider">{item.label}</dt>
                      <dd className="mt-1 text-sm font-medium text-slate-900 dark:text-white">{item.value}</dd>
                    </div>
                  ))}
                </dl>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
