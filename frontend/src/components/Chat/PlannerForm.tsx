import { useState, type FormEvent } from "react";
import { Send } from "lucide-react";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { Button } from "@/components/ui/Button";
import { Input, Select } from "@/components/ui/Input";
import { InterestTags } from "./InterestTags";
import { FileUploadZone } from "./FileUploadZone";
import { usePlan } from "@/hooks/use-plan";
import { SUPPORTED_CURRENCIES } from "@/utils/constants";
import type { PlanRequest } from "@/types/api";

export function PlannerForm() {
  const { isPlanning, submitPlan } = usePlan();

  const [destination, setDestination] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [budget, setBudget] = useState("5000");
  const [currency, setCurrency] = useState("USD");
  const [groupSize, setGroupSize] = useState("2");
  const [interests, setInterests] = useState<string[]>([]);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [pdfFile, setPdfFile] = useState<File | null>(null);

  function toggleInterest(value: string) {
    setInterests((prev) =>
      prev.includes(value) ? prev.filter((i) => i !== value) : [...prev, value],
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const req: PlanRequest = {
      destination,
      start_date: startDate,
      end_date: endDate,
      budget: Number(budget),
      currency,
      group_size: Number(groupSize),
      interests: interests.join(", "),
      audio_file: audioFile ?? undefined,
      image_file: imageFile ?? undefined,
      pdf_file: pdfFile ?? undefined,
    };
    await submitPlan(req);
  }

  return (
    <GlassPanel className="mx-auto max-w-2xl">
      <form onSubmit={handleSubmit} className="space-y-5">
        <div>
          <h2 className="font-heading text-xl font-bold text-slate-100">
            Plan Your Trip
          </h2>
          <p className="mt-1 text-sm text-slate-500">
            Tell us about your dream vacation
          </p>
        </div>

        <Input
          label="Destination"
          placeholder="e.g. Paris, Tokyo, Rio de Janeiro"
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          required
        />

        <div className="grid grid-cols-2 gap-3">
          <Input
            label="Start Date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
          <Input
            label="End Date"
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            required
          />
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input
            label="Budget"
            type="number"
            min={0}
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            required
          />
          <Select
            label="Currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
          >
            {SUPPORTED_CURRENCIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </Select>
          <Input
            label="Group Size"
            type="number"
            min={1}
            max={20}
            value={groupSize}
            onChange={(e) => setGroupSize(e.target.value)}
          />
        </div>

        <InterestTags selected={interests} onToggle={toggleInterest} />

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <FileUploadZone
            label="Audio"
            accept="audio/*"
            file={audioFile}
            onFileChange={setAudioFile}
          />
          <FileUploadZone
            label="Image"
            accept="image/*"
            file={imageFile}
            onFileChange={setImageFile}
          />
          <FileUploadZone
            label="PDF"
            accept=".pdf"
            file={pdfFile}
            onFileChange={setPdfFile}
          />
        </div>

        <Button
          type="submit"
          size="lg"
          loading={isPlanning}
          icon={<Send className="h-4 w-4" />}
          className="w-full"
        >
          {isPlanning ? "Planning your trip..." : "Start Planning"}
        </Button>
      </form>
    </GlassPanel>
  );
}
