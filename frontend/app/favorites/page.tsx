import JobExplorer from "@/components/JobExplorer";

export default function FavoritesPage() {
  return <section className="pageSection"><div className="eyebrow"><span>02</span> MY SHORTLIST</div><h1 className="pageTitle">관심에서 지원까지,<br /><em>놓치지 않게.</em></h1><JobExplorer favoriteOnly /></section>;
}
