import { KpiCard } from "./KpiCard";

type StatCardProps = {
  title: string;
  value: string | number;
  change?: string;
  changeType?: "positive" | "negative" | "neutral";
  icon?: React.ReactNode;
};

export function StatCard({ title, value, change, changeType, icon }: StatCardProps) {
  return (
    <KpiCard
      label={title}
      value={value}
      icon={icon}
      trend={
        change && changeType
          ? {
              direction:
                changeType === "positive"
                  ? "up"
                  : changeType === "negative"
                    ? "down"
                    : "neutral",
              label: change,
              positiveIsUp: true,
            }
          : undefined
      }
      semantic={
        changeType === "positive"
          ? "success"
          : changeType === "negative"
            ? "error"
            : "default"
      }
    />
  );
}