import { Suspense } from "react";
import ResearchScreen from "@/components/research/ResearchScreen";

export default function ResearchPage() {
  return (
    <Suspense fallback={null}>
      <ResearchScreen />
    </Suspense>
  );
}
