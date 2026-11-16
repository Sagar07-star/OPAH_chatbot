
import { useState } from "react";
import "./App.css";

const suggestions = [
  {
    number: "01",
    title: "Start a project",
    description: "Turn your creative idea into a production brief.",
    prompt: "I want to start a new production project.",
  },
  {
    number: "02",
    title: "Find creative talent",
    description: "Discover photographers and videographers.",
    prompt: "Help me find creative talent for my project.",
  },
  {
    number: "03",
    title: "Plan a shoot",
    description: "Build shot lists, concepts and creative plans.",
    prompt: "Help me plan a photoshoot.",
  },
];

function App() {
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);

  function sendMessage(e) {
    e.preventDefault();

    if (!message.trim()) return;

    setMessages((previous) => [
      ...previous,
      { role: "user", text: message.trim() },
    ]);

    setMessage("");
  }

  function startNewChat() {
    setMessages([]);
    setMessage("");
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">O</div>
          <span>OPAH <span className="brand-chat">CREATEchat</span></span>
        </div>

        <button className="new-chat" onClick={startNewChat}>
          <span>＋</span> New conversation
        </button>

        <div className="sidebar-section">
          <p className="section-label">// WORKSPACE</p>
          <button className="nav-item active">◈ General chat</button>
          <button className="nav-item">▣ My projects</button>
        </div>

        <div className="sidebar-section">
          <p className="section-label">// RECENT</p>
          <p className="empty-history">Your conversations will appear here.</p>
        </div>

        <div className="profile">
          <div className="avatar">S</div>
          <div className="profile-info">
            <strong>Sagar</strong>
            <span>Client account</span>
          </div>
          <span className="profile-menu">•••</span>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <p className="topbar-label">// YOUR WORKSPACE</p>
            <h3>General conversation</h3>
          </div>

          <button className="project-select">
            Select a project <span>⌄</span>
          </button>
        </header>

        <section className="chat-area">
          <div className="chat-content">
            {messages.length === 0 ? (
              <div className="welcome">
                <div className="welcome-icon">✳</div>
                <p className="welcome-label">// YOUR CREATIVE PARTNER</p>

                <h1>
                  Let's make
                  <br />
                  something <span>great.</span>
                </h1>

                <p className="welcome-description">
                  From the first idea to the final deliverable,
                  CREATEchat helps you bring your production to life.
                </p>

                <div className="suggestion-heading">
                  <span>// WHERE SHOULD WE START?</span>
                </div>

                <div className="suggestions">
                  {suggestions.map((item) => (
                    <button
                      className="suggestion-card"
                      key={item.number}
                      onClick={() => setMessage(item.prompt)}
                    >
                      <span className="suggestion-number">{item.number}</span>
                      <span className="suggestion-arrow">↗</span>
                      <strong>{item.title}</strong>
                      <small>{item.description}</small>
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="messages">
                {messages.map((item, index) => (
                  <div className={`message-row ${item.role}`} key={index}>
                    <div className="message-bubble">{item.text}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="composer-wrapper">
            <form className="composer" onSubmit={sendMessage}>
              <button
                type="button"
                className="attach-button"
                title="Attach files"
              >
                ＋
              </button>

              <input
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Tell us what you're looking to create..."
              />

              <button
                className="send-button"
                type="submit"
                disabled={!message.trim()}
              >
                ↑
              </button>
            </form>

            <p className="disclaimer">
              CREATEchat is your production assistant. Review important
              details before approving changes.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;
