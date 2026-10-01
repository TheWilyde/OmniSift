"use client";

import { useAuthStore } from "@/lib/store";
import { ChevronDown, User, Shield, Briefcase, Scale, Gavel, Users } from "lucide-react";
import { useState } from "react";

const ROLE_LABELS: Record<string, string> = {
  general: "General",
  finance: "Finance",
  legal: "Legal",
  admin: "Admin",
  hr: "Human Resources",
};

const ROLE_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  general: User,
  finance: Briefcase,
  legal: Scale,
  admin: Shield,
  hr: Users,
};

const VALID_ROLES = ["general", "finance", "legal", "admin", "hr"] as const;

export function RoleSwitcher() {
  const { impersonateRole, setImpersonateRole } = useAuthStore();
  const [isOpen, setIsOpen] = useState(false);

  const currentRole = impersonateRole || "general";
  const CurrentIcon = ROLE_ICONS[currentRole] || User;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label="Switch role"
      >
        <CurrentIcon className="w-4 h-4 text-gray-600 dark:text-gray-400" />
        <span className="text-sm font-medium text-gray-700 dark:text-gray-300 capitalize">
          {ROLE_LABELS[currentRole]}
        </span>
        <ChevronDown className={`w-4 h-4 text-gray-500 transition-transform ${isOpen ? "rotate-180" : ""}`} />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
            aria-hidden="true"
          />
          <div className="absolute right-0 mt-1 w-48 z-50 rounded-md bg-white dark:bg-gray-800 shadow-lg ring-1 ring-black ring-opacity-5 divide-y divide-gray-100 dark:divide-gray-700">
            {VALID_ROLES.map((role) => {
              const RoleIcon = ROLE_ICONS[role] || User;
              return (
                <button
                  key={role}
                  type="button"
                  onClick={() => {
                    setImpersonateRole(role);
                    setIsOpen(false);
                  }}
                  className={`w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors ${
                    role === currentRole
                      ? "bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300"
                      : "text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                  }`}
                  role="option"
                  aria-selected={role === currentRole}
                >
                  <RoleIcon className={`w-4 h-4 ${role === currentRole ? "text-blue-600 dark:text-blue-400" : "text-gray-400"}`} />
                  <span className="capitalize">{ROLE_LABELS[role]}</span>
                  {role === currentRole && (
                    <svg className="ml-auto w-4 h-4 text-blue-600 dark:text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  )}
                </button>
              );
            })}
            <div className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400 border-t border-gray-100 dark:border-gray-700">
              Development mode only
            </div>
          </div>
        </>
      )}
    </div>
  );
}