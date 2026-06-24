"use client";

import { useState } from "react";

const contactEmail = "vjihyun.bangv@gmail.com";

export default function SiteFooter() {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [sender, setSender] = useState("");
  const [message, setMessage] = useState("");

  const subject = encodeURIComponent(`[JobRadar] 문의${name.trim() ? ` - ${name.trim()}` : ""}`);
  const bodyText = [
    name.trim() ? `이름: ${name.trim()}` : "",
    sender.trim() ? `회신 이메일: ${sender.trim()}` : "",
    "",
    message.trim() || "안녕하세요. JobRadar 관련해서 문의드립니다.",
  ].filter((line, index) => index >= 2 || line).join("\n");
  const body = encodeURIComponent(bodyText);
  const gmailUrl = `https://mail.google.com/mail/?${new URLSearchParams({
    view: "cm",
    fs: "1",
    to: contactEmail,
    su: `[JobRadar] 문의${name.trim() ? ` - ${name.trim()}` : ""}`,
    body: bodyText,
  }).toString()}`;
  const mailtoUrl = `mailto:${contactEmail}?subject=${subject}&body=${body}`;

  function closeModal() {
    setOpen(false);
    setName("");
    setSender("");
    setMessage("");
  }

  function openGmail() {
    window.open(gmailUrl, "_blank", "noopener,noreferrer");
    closeModal();
  }

  function openMailto() {
    window.location.href = mailtoUrl;
    closeModal();
  }

  return (
    <footer className="siteFooter">
      <div>
        <strong>JOB RADAR</strong>
        <span>최근 업데이트 2026.06.24 · 지원 결정을 더 빠르게 만드는 개인 채용 레이더</span>
      </div>
      <div className="footerLinks">
        <a href="https://github.com/tami-bang" target="_blank" rel="noreferrer">GitHub</a>
        <button type="button" onClick={() => setOpen(true)}>{contactEmail}</button>
      </div>

      {open && (
        <div className="modalBackdrop" role="presentation" onMouseDown={closeModal}>
          <div className="emailModal contactModal" role="dialog" aria-modal="true" aria-labelledby="contact-modal-title" onMouseDown={(event) => event.stopPropagation()}>
            <button className="modalClose" aria-label="닫기" onClick={closeModal}>×</button>
            <span className="modalKicker">CONTACT</span>
            <h3 id="contact-modal-title">메일 보내기</h3>
            <div className="contactFields">
              <input aria-label="이름" placeholder="이름" value={name} onChange={(event) => setName(event.target.value)} />
              <input aria-label="회신 이메일" placeholder="회신 이메일" type="email" value={sender} onChange={(event) => setSender(event.target.value)} />
              <textarea aria-label="문의 내용" placeholder="문의 내용을 입력하세요" value={message} onChange={(event) => setMessage(event.target.value)} />
            </div>
            <button className="scanButton wide contactSubmit" type="button" onClick={openGmail}>Gmail로 열기</button>
            <button className="mailFallback contactSubmit" type="button" onClick={openMailto}>기본 메일 앱으로 열기</button>
            <small>Gmail 작성창을 새 탭으로 열고, 닫으면 입력 내용은 초기화됩니다.</small>
          </div>
        </div>
      )}
    </footer>
  );
}
