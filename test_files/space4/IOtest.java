import java.io.*;

public class IOTest
{
    public static void main(String[] args) {
        try {
            File f = new File("scratch");
            PrintWriter ps = new PrintWriter(new OutputStreamWriter
                                             (new FileOutputStream(f)));
            for (int i = 0; i < 1000000; i++) {
                ps.print(String.valueOf(i));
            }
            ps.close();
        }
        catch(IOException ioe) {
            ioe.printStackTrace();
        }
    }
}

