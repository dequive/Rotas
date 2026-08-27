"use client";

import type { KeyboardEvent } from "react";
import { useState } from "react";
import TabOverview from "./TabOverview";
import TabWorkshop from "./TabWorkshop";
import TabFinance from "./TabFinance";
import TabAdmin from "./TabAdmin";
import { Activity, Wrench, DollarSign, FileText } from "lucide-react";

type TabId = "overview" | "workshop" | "finance" | "admin";

export default function VehicleTabsClient({ 
  vehicleId, 
  assignmentList, 
  documents 
}: { 
  vehicleId: string; 
  assignmentList: any[]; 
  documents: any[] 
}) {
  const [activeTab, setActiveTab] = useState<TabId>("overview");

  const tabs = [
    { id: "overview", label: "Operação", icon: <Activity size={18} /> },
    { id: "workshop", label: "Oficina", icon: <Wrench size={18} /> },
    { id: "finance", label: "Financeiro", icon: <DollarSign size={18} /> },
    { id: "admin", label: "Administração", icon: <FileText size={18} /> }
  ];

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) {
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % tabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = tabs.length - 1;
    if (nextIndex === null) return;
    event.preventDefault();
    const next = tabs[nextIndex];
    setActiveTab(next.id as TabId);
    event.currentTarget
      .closest('[role="tablist"]')
      ?.querySelector<HTMLButtonElement>(`#vehicle-tab-${next.id}`)
      ?.focus();
  }

  return (
    <div>
      {/* Tab Navigation */}
      <div
        role="tablist"
        aria-label="Detalhes da viatura"
        className="flex overflow-x-auto bg-slate-100 p-1.5 rounded-2xl mb-8 space-x-1 border border-slate-200/60 shadow-inner"
      >
        {tabs.map((tab, index) => {
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              id={`vehicle-tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`vehicle-panel-${tab.id}`}
              tabIndex={isActive ? 0 : -1}
              onClick={() => setActiveTab(tab.id as TabId)}
              onKeyDown={(event) => handleTabKeyDown(event, index)}
              className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-bold transition-all duration-200 ${
                isActive 
                  ? "bg-white text-indigo-700 shadow-sm ring-1 ring-slate-900/5" 
                  : "text-slate-500 hover:text-slate-900 hover:bg-slate-200/50"
              }`}
            >
              <span aria-hidden="true" className={isActive ? "text-indigo-600" : "text-slate-400"}>
                {tab.icon}
              </span>
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab Content Area */}
      <div
        id={`vehicle-panel-${activeTab}`}
        role="tabpanel"
        aria-labelledby={`vehicle-tab-${activeTab}`}
        tabIndex={0}
        className="min-h-[400px]"
      >
        {activeTab === "overview" && <TabOverview vehicleId={vehicleId} />}
        {activeTab === "workshop" && <TabWorkshop vehicleId={vehicleId} />}
        {activeTab === "finance" && <TabFinance vehicleId={vehicleId} />}
        {activeTab === "admin" && <TabAdmin vehicleId={vehicleId} assignmentList={assignmentList} documents={documents} />}
      </div>
    </div>
  );
}
