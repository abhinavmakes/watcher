import { ClusterDetailView } from "@/components/cluster/cluster-detail-view";

// Next 16: params is async. Thin server page unwraps it and hands the id to the
// client view, which does the SWR fetch (client-side, per the API design).
export default async function ClusterPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <ClusterDetailView id={id} />;
}
