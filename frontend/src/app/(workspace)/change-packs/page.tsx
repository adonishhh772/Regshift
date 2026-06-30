import { SessionListView } from "@/components/SessionListView";

export default function ChangePacksPage() {
  return (
    <SessionListView
      title="Change Packs"
      description="Approval-ready change packs generated from completed sessions."
      filter="change-packs"
    />
  );
}
