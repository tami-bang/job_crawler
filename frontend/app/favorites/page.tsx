import JobExplorer from "@/components/JobExplorer";

export default function FavoritesPage() {
  return <section className="pageSection"><div className="eyebrow"><span>02</span> MY SHORTLIST</div><h1 className="pageTitle text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-white break-keep"><span>관심에서 지원까지, </span><span className="inline-block [color:var(--lime)]">놓치지 않게.</span></h1><JobExplorer favoriteOnly /></section>;
}
