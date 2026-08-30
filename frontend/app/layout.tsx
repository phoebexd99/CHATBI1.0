import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "CHATBI — 上传数据，直接问数",
  description: "上传 Excel 或 CSV，用自然语言获得数字、图表、明细和简单解读。",
};

const links = [
  ["/", "智能问数"],
  ["/knowledge", "知识中心"],
  ["/evaluations", "评测中心"],
];

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <aside className="sidebar">
          <Link className="brand" href="/">
            <span className="brand-mark">C</span>
            <span><strong>CHATBI</strong><small>Certified intelligence</small></span>
          </Link>
          <nav>
            {links.map(([href, label], index) => <Link href={href} key={href}><span>0{index + 1}</span>{label}</Link>)}
          </nav>
          <div className="sidebar-foot">
            <span className="pulse" />
            <div><strong>经营分析助手在线</strong><small>Excel / CSV · 电商演示模板</small></div>
          </div>
        </aside>
        <main>{children}</main>
      </body>
    </html>
  );
}

