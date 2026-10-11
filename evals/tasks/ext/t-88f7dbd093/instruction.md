RBAC with Domain model ,get_all_subjects error
1、model.conf
![image](https://github.com/casbin/pycasbin/assets/32121721/9cd37638-a702-4138-8544-50fbdaa0e55f)
2、code：
![image](https://github.com/casbin/pycasbin/assets/32121721/5041e3a1-af32-41a5-8895-227289c759b2)
3、sqlite info
![image](https://github.com/casbin/pycasbin/assets/32121721/f66c78a6-a64c-43fe-9985-e18edde72b65)

question:
e.get_all_objects()  --> ['test.xxx.com']
it should be ['system:get','system:put','system:post']
