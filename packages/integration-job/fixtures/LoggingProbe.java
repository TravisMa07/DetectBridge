import java.lang.reflect.Method;

/** Original synthetic privacy regression, executed against the deployed Log4j backend. */
public final class LoggingProbe {
  private static Throwable failure(boolean custom) {
    if (custom) {
      return new IllegalArgumentException("private-body-sentinel α \"secret\"") {
        @Override public String toString() { return "private-body-sentinel"; }
      };
    }
    return new IllegalStateException("java.lang.OutOfMemoryError: private-body-sentinel α \"secret\"\nextra",
        new RuntimeException("private-body-sentinel"));
  }
  private static Throwable oomFailure(boolean wrapped) {
    Throwable error = new OutOfMemoryError("private-body-sentinel");
    return wrapped ? new RuntimeException("private-body-sentinel", error) : error;
  }
  public static void main(String[] args) throws Exception {
    Class<?> manager = Class.forName("org.apache.logging.log4j.LogManager");
    Object logger = manager.getMethod("getLogger", String.class).invoke(null, "detectbridge.logging.probe");
    Method error = Class.forName("org.apache.logging.log4j.Logger")
        .getMethod("error", String.class, Throwable.class);
    error.invoke(logger, "private-body-sentinel", null);
    error.invoke(logger, "private-body-sentinel", failure(false));
    error.invoke(logger, "private-body-sentinel", failure(true));
    error.invoke(logger, "private-body-sentinel", oomFailure(false));
    error.invoke(logger, "private-body-sentinel", oomFailure(true));
    error.invoke(logger, "private-body-sentinel", null);
  }
}
