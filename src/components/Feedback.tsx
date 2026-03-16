import React, { useEffect, useState } from "react";

type FeedbackData = {
  rating: number;
  category: "bug" | "feature" | "design" | "performance" | "other";
  message: string;
  email?: string;
  timestamp: string;
  userAgent?: string;
};

const FEEDBACK_CATEGORIES = [
  {
    value: "bug",
    label: "Bug Report",
    emoji: "🐛",
    color: "bg-red-100 text-red-800",
  },
  {
    value: "feature",
    label: "Feature Request",
    emoji: "💡",
    color: "bg-blue-100 text-blue-800",
  },
  {
    value: "design",
    label: "Design Feedback",
    emoji: "🎨",
    color: "bg-purple-100 text-purple-800",
  },
  {
    value: "performance",
    label: "Performance",
    emoji: "⚡",
    color: "bg-green-100 text-green-800",
  },
  {
    value: "other",
    label: "Other",
    emoji: "💬",
    color: "bg-gray-100 text-gray-800",
  },
];

const ratingLabels = ["Very Poor", "Poor", "Average", "Good", "Excellent"];

const Feedback: React.FC = () => {
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  const [feedbackForm, setFeedbackForm] = useState<FeedbackData>({
    rating: 5,
    category: "other",
    message: "",
    email: "",
    timestamp: new Date().toISOString(),
    userAgent: typeof navigator !== "undefined" ? navigator.userAgent : "",
  });

  const [hoveredRating, setHoveredRating] = useState<number | null>(null);

  useEffect(() => {
    if (showFeedbackModal) {
      document.body.style.overflow = "hidden";
      document.documentElement.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "unset";
      document.documentElement.style.overflow = "unset";
    }
    return () => {
      document.body.style.overflow = "unset";
      document.documentElement.style.overflow = "unset";
    };
  }, [showFeedbackModal]);

  const handleFeedbackSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!feedbackForm.message.trim()) {
      alert("Please enter your feedback message.");
      return;
    }

    setFeedbackLoading(true);

    setTimeout(() => {
      console.log("📝 Feedback Submitted:", feedbackForm);
      setFeedbackLoading(false);
      setFeedbackSubmitted(true);
      setTimeout(() => {
        setShowFeedbackModal(false);
        setFeedbackSubmitted(false);
        setFeedbackForm({
          rating: 5,
          category: "other",
          message: "",
          email: "",
          timestamp: new Date().toISOString(),
          userAgent:
            typeof navigator !== "undefined" ? navigator.userAgent : "",
        });
      }, 2000);
    }, 800);
  };

  return (
    <>
      {!showFeedbackModal && (
        <button
          onClick={() => setShowFeedbackModal(true)}
          className="fixed bottom-6 right-6 z-40 flex items-center gap-3 px-5 py-4 rounded-full bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 text-white font-semibold shadow-2xl hover:shadow-3xl transform hover:scale-105 transition group animate-bounce-slow"
          aria-label="Open feedback form"
          title="Share your feedback"
        >
          <div className="relative">
            <svg
              className="w-6 h-6 group-hover:rotate-12 transition"
              viewBox="0 0 24 24"
              fill="currentColor"
            >
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm3.5-9c.83 0 1.5-.67 1.5-1.5S16.33 8 15.5 8 14 8.67 14 9.5s.67 1.5 1.5 1.5zm-7 0c.83 0 1.5-.67 1.5-1.5S9.33 8 8.5 8 7 8.67 7 9.5 7.67 11 8.5 11zm3.5 6.5c2.33 0 4.31-1.46 5.11-3.5H6.89c.8 2.04 2.78 3.5 5.11 3.5z" />
            </svg>
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-red-400 rounded-full animate-ping"></div>
          </div>
          <span className="hidden sm:inline font-bold">Feedback</span>
        </button>
      )}

      {showFeedbackModal && (
        <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 overflow-hidden">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-md z-[9998]"
            onClick={() => !feedbackSubmitted && setShowFeedbackModal(false)}
          />

          <div
            role="dialog"
            aria-modal="true"
            className="relative z-[9999] bg-white w-full max-w-2xl rounded-3xl shadow-2xl max-h-[90vh] overflow-y-auto"
          >
            <div className="sticky top-0 z-50 bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 text-white p-6 rounded-t-3xl">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <h2 className="text-2xl font-extrabold mb-2">
                    Share Your Feedback
                  </h2>
                  <p className="text-white/90">
                    Help us improve the NCR Portal experience
                  </p>
                </div>
                {!feedbackSubmitted && (
                  <button
                    onClick={() => setShowFeedbackModal(false)}
                    className="flex-shrink-0 p-2 rounded-full bg-white/20 hover:bg-white/30 transition"
                    aria-label="Close feedback form"
                  >
                    <svg
                      className="w-5 h-5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                )}
              </div>
            </div>

            <div className="p-6">
              {feedbackSubmitted ? (
                <div className="text-center py-8">
                  <div className="w-20 h-20 rounded-full bg-gradient-to-br from-emerald-100 to-green-50 flex items-center justify-center mx-auto mb-6">
                    <svg
                      className="w-10 h-10 text-emerald-600"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      viewBox="0 0 24 24"
                    >
                      <path d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 mb-3">
                    Thank You! 🎉
                  </h3>
                  <p className="text-slate-600 mb-4">
                    Your feedback has been submitted successfully. We appreciate
                    your input and will use it to improve our services.
                  </p>
                  <button
                    onClick={() => setShowFeedbackModal(false)}
                    className="px-6 py-2 bg-gradient-to-r from-emerald-500 to-green-600 text-white font-semibold rounded-lg hover:shadow-lg transition"
                  >
                    Close
                  </button>
                </div>
              ) : (
                <form onSubmit={handleFeedbackSubmit} className="space-y-6">
                  <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-2xl p-6">
                    <label className="text-lg font-semibold text-slate-900 mb-4 block">
                      How would you rate your experience?
                    </label>
                    <div className="flex items-center justify-center gap-1 mb-3">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <button
                          key={star}
                          type="button"
                          onClick={() =>
                            setFeedbackForm({ ...feedbackForm, rating: star })
                          }
                          onMouseEnter={() => setHoveredRating(star)}
                          onMouseLeave={() => setHoveredRating(null)}
                          className="text-4xl transition-all duration-200 transform hover:scale-125 active:scale-95"
                        >
                          {(hoveredRating ?? feedbackForm.rating) >= star
                            ? "⭐"
                            : "☆"}
                        </button>
                      ))}
                    </div>
                    <div className="text-center">
                      <div className="text-lg font-bold text-amber-700 mb-1">
                        {ratingLabels[feedbackForm.rating - 1]}
                      </div>
                      <div className="text-sm text-slate-600">
                        {feedbackForm.rating === 5
                          ? "We're thrilled you had an excellent experience!"
                          : feedbackForm.rating === 1
                            ? "We're sorry to hear that. Please tell us more below."
                            : "Your feedback helps us improve!"}
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="text-lg font-semibold text-slate-900 mb-4 block">
                      What type of feedback do you have?
                    </label>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      {FEEDBACK_CATEGORIES.map((cat) => (
                        <button
                          key={cat.value}
                          type="button"
                          onClick={() =>
                            setFeedbackForm({
                              ...feedbackForm,
                              category: cat.value as any,
                            })
                          }
                          className={`p-4 rounded-xl border-2 transition-all duration-200 ${feedbackForm.category === cat.value ? `border-amber-500 bg-gradient-to-br from-amber-50 to-orange-50 ${cat.color}` : "border-slate-200 hover:border-amber-300 hover:bg-amber-50"}`}
                        >
                          <div className="text-2xl mb-2">{cat.emoji}</div>
                          <div className="text-sm font-medium">{cat.label}</div>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="text-lg font-semibold text-slate-900 mb-4 block">
                      Your Feedback *
                    </label>
                    <div className="relative">
                      <textarea
                        value={feedbackForm.message}
                        onChange={(e) =>
                          setFeedbackForm({
                            ...feedbackForm,
                            message: e.target.value,
                          })
                        }
                        placeholder="Please share your thoughts, suggestions, or concerns..."
                        className="w-full px-4 py-4 rounded-xl border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:bg-white transition resize-none"
                        rows={5}
                        required
                        maxLength={500}
                      />
                      <div className="absolute bottom-3 right-3 text-xs text-slate-500">
                        {feedbackForm.message.length}/500
                      </div>
                    </div>
                  </div>

                  <div>
                    <label className="text-lg font-semibold text-slate-900 mb-4 block">
                      Your Email (Optional)
                    </label>
                    <input
                      type="email"
                      value={feedbackForm.email}
                      onChange={(e) =>
                        setFeedbackForm({
                          ...feedbackForm,
                          email: e.target.value,
                        })
                      }
                      placeholder="your.email@example.com"
                      className="w-full px-4 py-3 rounded-xl border border-slate-200 bg-slate-50 focus:outline-none focus:ring-2 focus:ring-amber-400 focus:bg-white transition"
                    />
                    <p className="text-sm text-slate-500 mt-2">
                      Provide your email if you'd like us to follow up with you.
                    </p>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-3">
                    <button
                      type="button"
                      onClick={() => setShowFeedbackModal(false)}
                      className="flex-1 px-6 py-3 rounded-xl bg-slate-100 text-slate-900 font-semibold hover:bg-slate-200 transition"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={feedbackLoading || !feedbackForm.message.trim()}
                      className="flex-1 px-6 py-3 bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 text-white font-semibold rounded-xl hover:shadow-xl transition transform hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:transform-none flex items-center justify-center gap-2"
                    >
                      {feedbackLoading ? (
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
                          Submitting...
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
                            <path d="M12 19l-7-7 7-7m8 0l-7 7 7 7" />
                          </svg>
                          Submit Feedback
                        </>
                      )}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes bounce-slow { 0%,100%{ transform: translateY(0); } 50%{ transform: translateY(-10px); } }
        .animate-bounce-slow { animation: bounce-slow 2s infinite; }
      `}</style>
    </>
  );
};

export default Feedback;
