These are the minimal steps for this project to work.

*WARNING:* when setting up the various services and objects below,
it'll make things easier if you stick to the same region/availability zone.
The code in this project uses the `us-east-1` region (N. Virginia) and
the `us-east-1a` availability zone, but yours might be different.
 There are some places currently in the project where these values are hard-coded,
 so you might want to search for those now and replace them.



# IAM


* Create a group with AdministratorAccess policy (a built-in policy),
  say, `admins`.

* Create a user, say, `admin0`:
    
    * Add the user to the `admins` group.
    
    * Give the user **programmatic** access.
        
        * Download the `.csv` credentials file to a secure location, run
          ```shell
          $ chmod 400 <the .csv file>
          ```
          to prevent others from reading its contents.
        
    * You may also want to give the user the **AWS Management Console**
      (the web interface) access, since you shouldn't use the root user
      much, and you'd want to perform the remaining steps under a
      non-root user.
        
        * If you do that, make note of the login page link,
        and after you finish with creating the user,
        log out of **AWS Management Console** and log back in under
        the newly created user on the provided login page.



# S3


* Create a bucket,
  say, `s3-bucket`, (it should be a universally unique bucket name),
  so you'll probably need to be more creative.
  Keep it private (i.e., check all "Block public access..." checkboxes).



# VPC


* Create a VPC if one doesn't exist yet, say, `vpc-0`
  (it will have a multiple-digit numeral following the `vpc-` prefix,
  but we're keeping it short, for simplicity)<br/>
  The default VPC will probably have a /16 CIDR block size,
  but if you're creating a new VPC, a /28 size should more than suffice
    
    * In the associated Security Group, say, `sg-0`,
      add these **inbound** rules:
  
      | Type       | Protocol | Port | Source                      | Description  |
      | ---------- | -------- | ---- | --------------------------- | ------------ |
      | Custom TCP | TPC      | 22   | My IP                       | \<any notes> |
      | Custom TCP | TPC      | 5432 | Custom (use `vpc-0`'s CIDR) | \<any notes> |
      
        * **Custom TCP**, port 22&mdash;This allows
          SSH access from your local machine, you'll need it
        
        * **Custom TCP**, port 5432
          (unless you change the port when creating an RDS instance)&mdash;This allows
          the instances within your VPC to connect to the RDS database.
          You could also limit this access to a subnet or a specific EC2 instance by
          specifying the corresponding CIDR block

* Create a DynamoDB endpoint:

  This is for the lambda function to be able access the DynamoDB table from within the VPC
    
    * In the **Endpoints** tab, click **Create Endpoint**
    
    * On the next screen:
        
        * Set **Service Category** to **AWS Services**
        
        * From the **Service Name** list, select **com.amazonaws.\<your region>.dynamodb**
        
        * In the **VPC** drop-down, select `vpc-0`
        
        * Under **Configure route tables**, select the routing table associated with
          the subnets you're using.
          
          *NOTE:* If you're setting up the project from scratch,
          there will likely be just one routing table in the list.
          If not, you can go to the EC2 console and double check:
          the routing table should be associated with the subnet in which your EC2 instance
          was created
          (so you may want to defer creating the endpoint
          to after creating the EC2 instance, see below for more on creating the instance).
        
        * Use the **Full Access** policy

* Create an S3 endpoint

  This is for the lambda function to be able access the S3 bucket from within the VPC
    
    * In the **Endpoints** tab, click **Create Endpoint**
    
    * On the next screen:
        
        * Set **Service Category** to **AWS Services**
        
        * From the **Service Name** list, select **com.amazonaws.\<your region>.s3**
        
        * In the **VPC** drop-down, select `vpc-0`
        
        * Under **Configure route tables**, select the routing table associated with
          the subnets you're using.
          
          *NOTE:* If you're setting up the project from scratch,
          there will likely be just one routing table in the list.
          If not, you can go to the EC2 console and double check:
          the routing table should be associated with the subnet in which your EC2 instance
          was created
          (so you may want to defer creating the endpoint
          to after creating the EC2 instance, see below for more on creating the instance).
        
        * Use the **Full Access** policy
      

        
# EC2


* Create a `t2.micro` instance, say, `i-0`, using the `Ubuntu 18.04 LTS` AMI
  (not minimal). It can be found by searching `ubuntu` and selecting
  **Marketplace** (there will be  few hundred results,
  but this one should pretty close to the top)
    
    * Add to the existing security group, `sg-0`
    
    * Create a new key pair for ssh access,
      download the `.pem` key-pair file to a secure location, run
      
      ```bash
      $ chmod 400 <the .pem file>
      ```
      
      to prevent others from reading its contents
      (ssh also won't let you use this key pair later on
      if the permissions aren't set to owner-only access)
    
    * Create an Elastic IP, say, `eipalloc-0`, then associate it
      with the instance `i-0`. When this is done, you can ssh
      to that instance by running
      
      ```bash
      $ ssh ubuntu@<the elastic IP> -i <the .pem file>
      ```



## EC2 Instance


* ssh into the instance, and update ubuntu:
  
  ```bash
  $ sudo apt update
  $ sudo apt upgrade
  ```
   
* Install python3 and pip3:
  
  ```bash
  $ sudo apt python3, python3-pip
  ```

* Install `awscli`:
  
  ```bash
  $ pip3 install --user --upgrade awscli
  ```

* Install DASH, for running the web page.
  You'll need to do this with `sudo` if you're planning to run your DASH page on port `80`:
  
  ```bash
  $ pip3 install dash \
                 dash-core-components \
                 dash-html-components \
                 dash-table \
                 dash-daq 
  ```

* Update the environment:
  
  ```bash
  $ source ~/.profile
  ```

* You may want to install PostgreSQL CLI to test the instance's
  connection to the RDS later on:
  
  ```bash
  $ sudo apt install postgresql
  ``` 


 
# RDS


* Create a PostgreSQL database
    
    * Choose a name for the database instance and an admin user name
    * Choose `vpc-0` as the **VPC**
    * Choose the **default** Subnet
    * Choose **No** for public accessibility
    * Select **Choose existing VPC security groups**, then select **default**
    * Disable IAM DB authentication
    * Might need to grant RDS Service Linked Role some permissions in IAM
      to let it push logs to Cloud Watch

* After the instance is created, go to instance details and make note
  of the **Endpoint** in the **Connect** section. You'll use it to
  connect to your database.
  If you set up an inbound rule in your security group, `sg-0`,
  as described above, and installed PostgreSQL on your instance, `i-0`,
  you should be able to connect to your database on the database instance
  from `i-0`:
  
  ```bash
  $ psql -h '<endpoint from the DB`s Connect section>' \
         -p 5432 \
         -U '<DB admin user name>'
  ```
    
    * If you don't see any messages for a while, your security group's
      inbound rules probably haven't been set up properly
    
    * When you see the prompt, enter the DB user's password
    
    * You can also save the password in the `PGPASSWORD` environment
      variable, to avoid typing it in every time
      you connect. Add this line to the end of the `~/.bashrc` file:
      
      ```bash
      export PGPASSWORD='<DB user`s password>'
      ```
      
      Then run this from the command line:
      
      ```bash
      $ source ~/.bashrc
      ```


      
# DynamoDB


* Create a table. For this project, call it `TrafficSpeed`
    
    * Type in the Primary Key name, `measurementSiteReference`
    (select the **String** type in the drop-down)
    
    * Check the **Add sorting key** checkbox,
    and type in the Sorting Key name, `measurementTimeDefault` (also **String**)
    
    * Uncheck the **Use default settings** checkbox, and select the following underneath it:
        
        * Select **Provisioned** capacity
        
        * Under **Auto Scaling**, increase the **Minimum provisioned capacity** for
          both reading and writing to 200 units
          (this costs more, but you can update this number later, after the table has been used,
          and you'll have seen how much of the capacity is actually used)
        
        * For the **IAM Role**, select **DynamoDB AutoScaling Service Linked Role**


        
# Lambda


* Create a function (select **Author from scratch**), fill in the following:
    
    * **Name:** `preprocess_xml`
    * **Runtime:** Python 3.6
      
      The packaged `psycopg2` module is precompiled for 3.6, and if you'd like a different
      runtime version of Python, you'll probably need to rebuild `psycopg2`, see the
      [awslambda-psycopg2](https://github.com/jkehler/awslambda-psycopg2) repo on GitHub
      for more details
      
    * **Role:** Create a new role from one or more templates
        * **Role name:** type in some name, say, `TrafficSpeedLambdaRole`
        * From **Policy templates**, select **Amazon S3 object read-only permissions**
        
    * Go to **IAM** console, locate the `TrafficSpeedLambdaRole` role, and add the following
      policies:
        
        * **AWSLambdaVPCAccessExecutionRole**, which will allow the lambda access
          the resources within the same VPC

* Configure the lambda using the **Designer**:
    
    * From the list of services on the left, select **S3**.
      This will add an **S3** card to the triggers in the diagram in the middle.<br/>
      Lower, under the **Configure triggers** section:
        
        * Select the S3 bucket you created earlier
          (the one referred to as `s3-bucket` above, in the S3 setup section)
        * In **Event type**, select **All object create events**
        * Keep **Prefix** and **Suffix** empty
        * Check **Enable trigger**
        * Click **Add**
    
    * In the **Designer** diagram, click the card with
      the **&lambda;** icon and the function's name, to switch to the code editor.
        
    * In **Function code** section, update the **Handler** field with
      `lambda_function_xml.main`.<br/>
     
      You might see a warning message saying that
      `lambda_function_xml.main` is not found, that's fine,
      the warning will disappear once the function code has been uploaded (see below).
    
    * Scroll down below the **Function Code** section, and:
        
        * In **Environment variables**, add the `PGPASSWORD` variable with
          the value of the user password as you used when setting up RDS 
        
        * In **Basic settings**, increase the **Memory** and **Timeout** values
          to their maximums.<br/>
          This shouldn't affect the cost, but will make sure the function doesn't timeout
          because of lack of resources
        
        * In **Network**:
            
            * In **VPC**, select `vpc-0`
            * In **Subnets**, select all the subnets in the list
              (it's a multiple-selection list)
            * In **Security groups**, select the security groups<br/>
              You'll see the inbound and outbound rules underneath.
              Double check that the lambda will be accessible from your local machine,
              for updating the function code, and from your VPC
    
    * Above the designer diagram, click **Save**

* Upload the function code by running from the project's root:
  ```bash
  $ ./upload-lambda-xml.sh
  ```
    
    * After this step, reload the code editor page and double check
      the memory, timeout, VPC and other settings (sometimes they seem to reset on upload)
        
 