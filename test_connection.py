"""
اختبار الاتصال بقاعدة البيانات Supabase
Test Supabase Connection
"""

try:
    from supabase import create_client, Client
    print("✅ مكتبة Supabase مثبتة بنجاح")
except ImportError:
    print("❌ مكتبة Supabase غير مثبتة")
    print("قم بتثبيتها باستخدام: pip install supabase")
    exit(1)

# بيانات الاتصال
SUPABASE_URL = "https://twnpufintlopmdndvpye.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InR3bnB1ZmludGxvcG1kbmR2cHllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTk4NDc3NjYsImV4cCI6MjA3NTQyMzc2Nn0.vTop5mq9MpTvqAv-hE_laDoIAZ9s15up6aQqkKJyQxg"

print("\n🔄 جاري الاتصال بقاعدة البيانات...")

try:
    # إنشاء اتصال
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    print("✅ تم الاتصال بنجاح!")

    # اختبار قراءة البيانات
    print("\n📊 جاري جلب بيانات التفعيلات...")
    result = supabase.table("activations").select("*").execute()

    if result.data:
        print(f"✅ تم العثور على {len(result.data)} تفعيل(ات)")
        print("\n📋 التفعيلات الموجودة:")
        print("-" * 80)
        for activation in result.data:
            status = "🚫 محظور" if activation.get('is_blocked') else ("✅ نشط" if activation.get('activated') else "❌ غير نشط")
            expiry = activation.get('expiry', 'مدى الحياة')
            print(f"• {activation.get('username')} - {status} - انتهاء: {expiry}")
        print("-" * 80)
    else:
        print("ℹ️  لا توجد تفعيلات حالياً")

    print("\n✅ نظام التحكم عن بُعد جاهز للاستخدام!")
    print("\n📝 الخطوات التالية:")
    print("1. شغل البرنامج: python remote_activation.py")
    print("2. افتح لوحة التحكم: admin_panel.html")
    print("3. اقرأ الدليل الكامل: REMOTE_CONTROL_GUIDE.md")

except Exception as e:
    print(f"❌ خطأ في الاتصال: {str(e)}")
    print("\n🔧 تأكد من:")
    print("1. اتصالك بالإنترنت")
    print("2. صحة بيانات الاتصال")
    print("3. تثبيت المكتبة: pip install supabase")
