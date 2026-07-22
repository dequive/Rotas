"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { SidebarLayout } from "../../../components/SidebarLayout";
import { PhotoEvidenceUploader } from "../../components/PhotoEvidenceUploader";
import SignatureCanvas from "../../components/SignatureCanvas";
import VehicleHistoryPanel from "../../components/VehicleHistoryPanel";

export default function NovaRecepcaoPage() {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // 1. Tipo de Propriedade da Viatura: Frota vs Cliente Comercial
  const [ownershipType, setOwnershipType] = useState<"fleet" | "customer">("customer");

  // 2. Tipo de Cliente: Indivíduo vs Organização (Default: individual)
  const [clientType, setClientType] = useState<"individual" | "organization">("individual");
  const [clientName, setClientName] = useState("João Muchanga");
  const [clientPhone, setClientPhone] = useState("+258 84 123 4567");

  // 3. Viatura selecionada e Odómetro Baseline
  const [selectedVehicleId, setSelectedVehicleId] = useState<string>("veh-demo-01");
  const [vehiclePlate, setVehiclePlate] = useState("AFM-8821-TR");
  const [odometerKm, setOdometerKm] = useState<number>(48500);
  const lastKnownOdometer = 48500; // Leitura de referência histórica

  // 4. Contactos Rastreáveis de Entrega & Levantamento
  const [deliveredByName, setDeliveredByName] = useState("João Muchanga");
  const [deliveredByPhone, setDeliveredByPhone] = useState("+258 84 123 4567");
  const [pickupAuthorizedByName, setPickupAuthorizedByName] = useState("João Muchanga");
  const [pickupAuthorizedByPhone, setPickupAuthorizedByPhone] = useState("+258 84 123 4567");
  const [isAutoFilled, setIsAutoFilled] = useState(true);

  // 5. Sintomas e Condição Visual
  const [reportedIssues, setReportedIssues] = useState("");
  const [visualCondition, setVisualCondition] = useState("");
  const [personalItems, setPersonalItems] = useState("");
  const [fuelLevel, setFuelLevel] = useState("half");

  // 6. Evidências Fotográficas e Assinatura
  const [photoFileIds, setPhotoFileIds] = useState<string[]>([]);
  const [signatureFileId, setSignatureFileId] = useState<string | null>(null);

  // Manipulador de Auto-preenchimento ao Mudar Tipo de Cliente ou Nome
  const handleClientTypeChange = (type: "individual" | "organization") => {
    setClientType(type);
    if (type === "individual") {
      setDeliveredByName(clientName);
      setDeliveredByPhone(clientPhone);
      setPickupAuthorizedByName(clientName);
      setPickupAuthorizedByPhone(clientPhone);
      setIsAutoFilled(true);
    } else {
      // Para Empresa/Organização, limpa para exigência de preenchimento do motorista/responsável
      setDeliveredByName("");
      setDeliveredByPhone("");
      setPickupAuthorizedByName("");
      setPickupAuthorizedByPhone("");
      setIsAutoFilled(false);
    }
  };

  const handleManualContactEdit = () => {
    setIsAutoFilled(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    const payload = {
      vehicle_id: selectedVehicleId,
      client_id: ownershipType === "customer" ? "client-demo-01" : null,
      odometer_at_reception: odometerKm,
      reported_issues: reportedIssues,
      visual_condition: visualCondition,
      personal_items: personalItems,
      fuel_level: fuelLevel,
      delivered_by_name: deliveredByName,
      delivered_by_phone: deliveredByPhone,
      pickup_authorized_by_name: pickupAuthorizedByName,
      pickup_authorized_by_phone: pickupAuthorizedByPhone,
      client_signature_file_id: signatureFileId,
    };

    try {
      const res = await fetch("/api/v1/workshop/receptions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        router.push(`/oficina/recepcao/${data.id || "REC-2026-0005"}`);
      } else {
        const err = await res.json();
        setErrorMessage(err.detail || "Erro ao gravar recepção de viatura.");
        setIsSubmitting(false);
      }
    } catch (err) {
      // Demo fallback redirect
      router.push("/oficina/recepcao/REC-2026-0005");
    }
  };

  const isOdometerWarning = odometerKm > 0 && odometerKm < lastKnownOdometer;

  return (
    <SidebarLayout active="recepcao">
      <div className="max-w-6xl mx-auto space-y-6 pb-12">
        {/* Cabeçalho da Página */}
        <div className="flex flex-col md:flex-row md:items-center justify-between border-b border-slate-200 pb-4 gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Nova Recepção de Viatura (Check-in)</h1>
            <p className="text-xs text-slate-500 mt-1">
              Entrada oficial na oficina • Emissão de sequência não-fiscal <code className="font-mono">REC-2026-XXXX</code>
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => router.back()}
              className="px-4 py-2 text-xs font-semibold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded border border-slate-300"
            >
              Cancelar
            </button>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 text-xs text-red-800 bg-red-50 border border-red-200 rounded-md">
            ⚠️ {errorMessage}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Coluna Principal: Formulário de Check-in em 2 terços */}
          <form onSubmit={handleSubmit} className="lg:col-span-2 space-y-6">
            {/* Bloco 1: Seleção de Origem & Cliente */}
            <div className="bg-white p-5 border border-slate-200 rounded-xl shadow-sm space-y-4">
              <h2 className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-2">
                1. Origem da Viatura & Titular do Registo
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Tipo de Propriedade</label>
                  <div className="flex space-x-2">
                    <button
                      type="button"
                      onClick={() => setOwnershipType("customer")}
                      className={`flex-1 py-2 px-3 text-xs font-semibold rounded border ${
                        ownershipType === "customer"
                          ? "bg-indigo-50 border-indigo-600 text-indigo-700"
                          : "bg-slate-50 border-slate-200 text-slate-600"
                      }`}
                    >
                      👤 Cliente Comercial
                    </button>
                    <button
                      type="button"
                      onClick={() => setOwnershipType("fleet")}
                      className={`flex-1 py-2 px-3 text-xs font-semibold rounded border ${
                        ownershipType === "fleet"
                          ? "bg-indigo-50 border-indigo-600 text-indigo-700"
                          : "bg-slate-50 border-slate-200 text-slate-600"
                      }`}
                    >
                      🚛 Frota Própria
                    </button>
                  </div>
                </div>

                {ownershipType === "customer" && (
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Tipo de Cliente</label>
                    <div className="flex space-x-2">
                      <button
                        type="button"
                        onClick={() => handleClientTypeChange("individual")}
                        className={`flex-1 py-2 px-3 text-xs font-semibold rounded border ${
                          clientType === "individual"
                            ? "bg-slate-800 text-white border-slate-800"
                            : "bg-slate-50 border-slate-200 text-slate-600"
                        }`}
                      >
                        Indivíduo (Particular)
                      </button>
                      <button
                        type="button"
                        onClick={() => handleClientTypeChange("organization")}
                        className={`flex-1 py-2 px-3 text-xs font-semibold rounded border ${
                          clientType === "organization"
                            ? "bg-slate-800 text-white border-slate-800"
                            : "bg-slate-50 border-slate-200 text-slate-600"
                        }`}
                      >
                        Organização / Empresa
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Autocomplete de Cliente */}
              {ownershipType === "customer" && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Nome do Cliente</label>
                    <input
                      type="text"
                      value={clientName}
                      onChange={(e) => setClientName(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                      placeholder="Pesquisar ou registar cliente..."
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Telefone Principal</label>
                    <input
                      type="text"
                      value={clientPhone}
                      onChange={(e) => setClientPhone(e.target.value)}
                      className="w-full px-3 py-2 text-xs border border-slate-300 rounded focus:ring-1 focus:ring-indigo-500"
                      placeholder="+258 8X XXX XXXX"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Bloco 2: Pessoas Rastreáveis de Entrega & Levantamento */}
            <div className="bg-white p-5 border border-slate-200 rounded-xl shadow-sm space-y-4">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <h2 className="text-sm font-bold text-slate-800">
                  2. Responsáveis pela Entrega & Levantamento Autorizado
                </h2>
                {isAutoFilled && clientType === "individual" && (
                  <span className="text-[11px] text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    ℹ️ Dados pré-preenchidos. Confirme com quem entregou.
                  </span>
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-3 bg-slate-50 p-3 rounded-lg border border-slate-100">
                  <h3 className="text-xs font-bold text-slate-700">Pessoa que Entregou a Viatura</h3>
                  <div>
                    <label className="block text-[11px] text-slate-600 mb-1">Nome de quem entregou</label>
                    <input
                      type="text"
                      value={deliveredByName}
                      onChange={(e) => {
                        setDeliveredByName(e.target.value);
                        handleManualContactEdit();
                      }}
                      className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded bg-white"
                      placeholder="ex: Carlos Sitoe (Motorista)"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-600 mb-1">Contacto Telefónico</label>
                    <input
                      type="text"
                      value={deliveredByPhone}
                      onChange={(e) => {
                        setDeliveredByPhone(e.target.value);
                        handleManualContactEdit();
                      }}
                      className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded bg-white"
                      placeholder="+258 8X XXX XXXX"
                    />
                  </div>
                </div>

                <div className="space-y-3 bg-slate-50 p-3 rounded-lg border border-slate-100">
                  <h3 className="text-xs font-bold text-slate-700">Pessoa Autorizada a Levantar</h3>
                  <div>
                    <label className="block text-[11px] text-slate-600 mb-1">Nome Autorizado no Release</label>
                    <input
                      type="text"
                      value={pickupAuthorizedByName}
                      onChange={(e) => {
                        setPickupAuthorizedByName(e.target.value);
                        handleManualContactEdit();
                      }}
                      className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded bg-white"
                      placeholder="ex: Dra. Maria Santos (Diretora)"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] text-slate-600 mb-1">Contacto Telefónico</label>
                    <input
                      type="text"
                      value={pickupAuthorizedByPhone}
                      onChange={(e) => {
                        setPickupAuthorizedByPhone(e.target.value);
                        handleManualContactEdit();
                      }}
                      className="w-full px-3 py-1.5 text-xs border border-slate-300 rounded bg-white"
                      placeholder="+258 8X XXX XXXX"
                    />
                  </div>
                </div>
              </div>
            </div>

            {/* Bloco 3: Dados da Viatura & Odómetro Baseline */}
            <div className="bg-white p-5 border border-slate-200 rounded-xl shadow-sm space-y-4">
              <h2 className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-2">
                3. Identificação & Odómetro Baseline
              </h2>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Matrícula da Viatura</label>
                  <input
                    type="text"
                    value={vehiclePlate}
                    onChange={(e) => setVehiclePlate(e.target.value)}
                    className="w-full px-3 py-2 text-xs border border-slate-300 rounded font-bold uppercase"
                    placeholder="AFM-8821-TR"
                    required
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Odómetro na Recepção (KM) *
                  </label>
                  <input
                    type="number"
                    value={odometerKm}
                    onChange={(e) => setOdometerKm(Number(e.target.value))}
                    className={`w-full px-3 py-2 text-xs border rounded font-semibold ${
                      isOdometerWarning ? "border-amber-500 bg-amber-50 text-amber-900" : "border-slate-300"
                    }`}
                    min={0}
                    required
                  />
                  {isOdometerWarning && (
                    <p className="text-[11px] text-amber-700 mt-1 font-medium">
                      ⚠️ Odómetro inferior ao último histórico registado ({lastKnownOdometer} km). Verifique digitação.
                    </p>
                  )}
                </div>
              </div>

              {/* Nível de Combustível */}
              <div>
                <label className="block text-xs font-medium text-slate-700 mb-2">Nível de Combustível</label>
                <div className="grid grid-cols-5 gap-2 text-center text-xs">
                  {[
                    { id: "empty", label: "Reserva (0%)" },
                    { id: "quarter", label: "1/4 (25%)" },
                    { id: "half", label: "1/2 (50%)" },
                    { id: "three_quarter", label: "3/4 (75%)" },
                    { id: "full", label: "Cheio (100%)" },
                  ].map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => setFuelLevel(item.id)}
                      className={`py-2 px-1 border rounded text-[11px] font-medium ${
                        fuelLevel === item.id
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-sm"
                          : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                      }`}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-1">Sintomas / Avarias Reportadas</label>
                <textarea
                  value={reportedIssues}
                  onChange={(e) => setReportedIssues(e.target.value)}
                  rows={2}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded"
                  placeholder="Descreva os ruídos, falhas de motor ou intervenções solicitadas pelo cliente..."
                />
              </div>
            </div>

            {/* Bloco 4: Fotos de Entrada & Assinatura */}
            <div className="bg-white p-5 border border-slate-200 rounded-xl shadow-sm space-y-4">
              <h2 className="text-sm font-bold text-slate-800 border-b border-slate-100 pb-2">
                4. Fotos de Danos Prévios & Assinatura
              </h2>

              <div>
                <label className="block text-xs font-medium text-slate-700 mb-2">
                  Fotografia de Entrada (Evidência com Hash SHA-256 no Servidor)
                </label>
                <PhotoEvidenceUploader
                  label="Fotografias de entrada"
                  onUpload={(photo) => setPhotoFileIds((prev) => [...prev, photo.id])}
                />
              </div>

              <SignatureCanvas
                onSignatureCaptured={(fileId: string) => setSignatureFileId(fileId)}
              />
            </div>

            {/* Botão de Submissão */}
            <div className="flex justify-end pt-2">
              <button
                type="submit"
                disabled={isSubmitting}
                className="px-6 py-3 text-sm font-bold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-md disabled:opacity-50"
              >
                {isSubmitting ? "A Registar Check-in..." : "Concluir Recepção & Gerar REC-2026-XXXX"}
              </button>
            </div>
          </form>

          {/* Coluna Lateral: Painel Vivo de Histórico em 1 terço */}
          <div className="lg:col-span-1">
            <VehicleHistoryPanel vehicleId={selectedVehicleId} />
          </div>
        </div>
      </div>
    </SidebarLayout>
  );
}
