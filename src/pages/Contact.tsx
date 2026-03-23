import React, { useState } from "react";
import { api } from "../services/api";

type InquiryForm = {
  name: string;
  email: string;
  subject: string;
  message: string;
};

// Feedback moved to a shared component

const DEFAULT_LOCATION = {
  address:
    "16th Floor, MMDA Head Office, Dofia Julia Vargas Avenue corner Molawe St., Barangay Ugong, Pasig City",
  lat: 14.5764,
  lng: 121.0851,
};

const Contact: React.FC = () => {
  const [inquiryForm, setInquiryForm] = useState<InquiryForm>({
    name: "",
    email: "",
    subject: "",
    message: "",
  });

  const [inquirySubmitted, setInquirySubmitted] = useState(false);
  const [inquiryLoading, setInquiryLoading] = useState(false);

  // feedback UI/logic was moved to `src/components/Feedback.tsx`

  const handleInquirySubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (
      !inquiryForm.name.trim() ||
      !inquiryForm.email.trim() ||
      !inquiryForm.message.trim()
    ) {
      alert("Please fill in all required fields.");
      return;
    }

    setInquiryLoading(true);
    try {
      await api.post("contact/", {
        name: inquiryForm.name.trim(),
        email: inquiryForm.email.trim(),
        subject: inquiryForm.subject.trim(),
        message: inquiryForm.message.trim(),
      });
      setInquirySubmitted(true);
      setTimeout(() => {
        setInquirySubmitted(false);
        setInquiryForm({
          name: "",
          email: "",
          subject: "",
          message: "",
        });
      }, 2000);
    } catch (error) {
      let message = "Failed to send your message. Please try again.";
      if (error instanceof Error && error.message) {
        try {
          const parsed = JSON.parse(error.message);
          message = parsed?.detail || error.message;
        } catch {
          message = error.message;
        }
      }
      alert(message);
    } finally {
      setInquiryLoading(false);
    }
  };

  // feedback submit handled in Feedback component

  const getMapEmbedUrl = () => {
    const { lat, lng } = DEFAULT_LOCATION;
    return `https://www.google.com/maps/embed/v1/place?key=AIzaSyBFw0Qbyq9zTFTd-tUY6dZWTgaQzuU17R8&q=${DEFAULT_LOCATION.address}&center=${lat},${lng}&zoom=16`;
  };

  // no local feedback modal state here

  return (
    <>
      <main className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
        {/* HEADER */}
        <header className="bg-gradient-to-r from-sky-600 via-sky-500 to-cyan-500 text-white">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
            <div className="text-center">
              <h1 className="text-4xl md:text-5xl font-extrabold mb-4">
                Contact RDC-NCR
              </h1>
              <p className="text-lg text-white/90 max-w-2xl mx-auto">
                Get in touch with the Regional Development Council - National
                Capital Region. We're here to help with inquiries, partnership
                opportunities, and collaborative projects.
              </p>
            </div>
          </div>
        </header>

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* CONTACT INFORMATION & MAP SECTION */}
          <section className="mb-12">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
              {/* Contact Info Card */}
              <div className="lg:col-span-1">
                <div className="bg-white rounded-3xl shadow-lg p-8 h-full">
                  <h2 className="text-2xl font-bold text-slate-900 mb-6">
                    Main Office Information
                  </h2>

                  <div className="space-y-6">
                    {/* Address */}
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-blue-100 to-blue-50 flex items-center justify-center flex-shrink-0">
                        <svg
                          className="w-6 h-6 text-blue-600"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
                          <path d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                        </svg>
                      </div>
                      <div>
                        <h4 className="font-semibold text-slate-900">
                          Address
                        </h4>
                        <p className="text-slate-600 text-sm mt-1">
                          {DEFAULT_LOCATION.address}
                        </p>
                      </div>
                    </div>

                    {/* Email */}
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-green-100 to-green-50 flex items-center justify-center flex-shrink-0">
                        <svg
                          className="w-6 h-6 text-green-600"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                      </div>
                      <div>
                        <h4 className="font-semibold text-slate-900">Email</h4>
                        <a
                          href="mailto:rdc.ncr@mmda.gov.ph"
                          className="text-blue-600 hover:underline text-sm"
                        >
                          rdc.ncr@mmda.gov.ph
                        </a>
                      </div>
                    </div>

                    {/* Phone */}
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-100 to-orange-50 flex items-center justify-center flex-shrink-0">
                        <svg
                          className="w-6 h-6 text-orange-600"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
                        </svg>
                      </div>
                      <div>
                        <h4 className="font-semibold text-slate-900">Phone</h4>
                        <a
                          href="tel:+632123456789"
                          className="text-blue-600 hover:underline text-sm"
                        >
                          +63 (2) 1234-5678
                        </a>
                      </div>
                    </div>

                    {/* Office Hours */}
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-100 to-purple-50 flex items-center justify-center flex-shrink-0">
                        <svg
                          className="w-6 h-6 text-purple-600"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                      </div>
                      <div>
                        <h4 className="font-semibold text-slate-900">
                          Office Hours
                        </h4>
                        <p className="text-slate-600 text-sm mt-1">
                          Monday - Friday: 7:00 AM - 4:00 PM
                          <br />
                          Saturday, Sunday & Holidays: Closed
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Map - Larger Section */}
              <div className="lg:col-span-2">
                <div className="bg-white rounded-3xl shadow-lg overflow-hidden h-full">
                  <div className="p-6 border-b border-slate-200">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                      <div>
                        <h3 className="text-xl font-bold text-slate-900">
                          RDC-NCR Location
                        </h3>
                        <p className="text-slate-600 text-sm mt-1">
                          MMDA Head Office, Pasig City
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="inline-flex items-center px-3 py-1 rounded-full bg-blue-100 text-blue-800 text-sm">
                          📍 Live Location
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Map Container */}
                  <div className="relative h-[500px] w-full">
                    <iframe
                      src={getMapEmbedUrl()}
                      width="100%"
                      height="100%"
                      style={{ border: 0 }}
                      allowFullScreen
                      loading="lazy"
                      referrerPolicy="no-referrer-when-downgrade"
                      title="RDC-NCR Location Map"
                      className="absolute inset-0"
                    />
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* INQUIRY FORM */}
          <section className="mb-12">
            <div className="bg-white rounded-3xl shadow-lg p-8">
              <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-slate-900 mb-2">
                  Send Us a Message
                </h2>
                <p className="text-slate-600 max-w-2xl mx-auto">
                  Have a question or inquiry? Fill out the form below and we'll
                  get back to you as soon as possible.
                </p>
              </div>

              {inquirySubmitted ? (
                <div className="text-center py-8">
                  <div className="w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-green-50 flex items-center justify-center mx-auto mb-4">
                    <svg
                      className="w-8 h-8 text-emerald-600"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <h3 className="text-lg font-bold text-slate-900">
                    Thank You!
                  </h3>
                  <p className="text-slate-600 mt-2">
                    Your inquiry has been received. We'll respond within 24-48
                    business hours.
                  </p>
                </div>
              ) : (
                <form onSubmit={handleInquirySubmit} className="space-y-6">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Name */}
                    <div>
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Full Name *
                      </label>
                      <input
                        type="text"
                        value={inquiryForm.name}
                        onChange={(e) =>
                          setInquiryForm({
                            ...inquiryForm,
                            name: e.target.value,
                          })
                        }
                        placeholder="Your full name"
                        className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:bg-white transition"
                        required
                      />
                    </div>

                    {/* Email */}
                    <div>
                      <label className="block text-sm font-semibold text-slate-900 mb-2">
                        Email Address *
                      </label>
                      <input
                        type="email"
                        value={inquiryForm.email}
                        onChange={(e) =>
                          setInquiryForm({
                            ...inquiryForm,
                            email: e.target.value,
                          })
                        }
                        placeholder="your.email@example.com"
                        className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:bg-white transition"
                        required
                      />
                    </div>
                  </div>

                  {/* Subject */}
                  <div>
                    <label className="block text-sm font-semibold text-slate-900 mb-2">
                      Subject
                    </label>
                    <input
                      type="text"
                      value={inquiryForm.subject}
                      onChange={(e) =>
                        setInquiryForm({
                          ...inquiryForm,
                          subject: e.target.value,
                        })
                      }
                      placeholder="What is your inquiry about?"
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:bg-white transition"
                    />
                  </div>

                  {/* Message */}
                  <div>
                    <label className="block text-sm font-semibold text-slate-900 mb-2">
                      Message *
                    </label>
                    <textarea
                      value={inquiryForm.message}
                      onChange={(e) =>
                        setInquiryForm({
                          ...inquiryForm,
                          message: e.target.value,
                        })
                      }
                      placeholder="Please describe your inquiry in detail..."
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-sky-400 focus:bg-white transition resize-none"
                      rows={6}
                      required
                    />
                  </div>

                  {/* Submit */}
                  <button
                    type="submit"
                    disabled={inquiryLoading}
                    className="w-full px-6 py-4 bg-gradient-to-r from-sky-500 to-cyan-500 text-white font-semibold rounded-xl hover:shadow-xl transition transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:transform-none flex items-center justify-center gap-2"
                  >
                    {inquiryLoading ? (
                      <>
                        <svg
                          className="w-5 h-5 animate-spin"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M12 2v4m0 12v4M4 12h4m12 0h4M5.64 5.64l2.83 2.83M15.53 15.53l2.83 2.83M5.64 18.36l2.83-2.83M15.53 8.47l2.83-2.83" />
                        </svg>
                        Sending...
                      </>
                    ) : (
                      <>
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          viewBox="0 0 24 24"
                        >
                          <path d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                        </svg>
                        Send Message
                      </>
                    )}
                  </button>
                </form>
              )}
            </div>
          </section>
        </div>
      </main>

      {/* Feedback is now provided by the shared `Feedback` component */}
    </>
  );
};

export default Contact;

